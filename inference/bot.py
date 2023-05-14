import os
import sys

INFERENCE_DIR = os.path.dirname(os.path.abspath(__file__))

# TODO: PYTHONPATH hacks are never a good idea. clean this up later
sys.path.append(os.path.join(INFERENCE_DIR, '..'))

import cmd
import torch
import argparse
import conversation as convo
import retrieval.wikipedia as wp
from transformers import AutoTokenizer, AutoModelForCausalLM, AutoConfig, StoppingCriteria, StoppingCriteriaList, BitsAndBytesConfig
from accelerate import infer_auto_device_map, init_empty_weights
import torch


def prepare_jit_inputs(inputs, model, tokenizer):
    num_batch = len(inputs)
    dummy_input = tokenizer.batch_encode_plus(inputs, return_tensors="pt", padding=True)
    num_block_layers, num_attention_heads, num_embedding_size_per_head = sparse_model_config(model.config)
    if model.config.model_type == "bloom":
        past_key_values = tuple(
            (
                torch.zeros(int(num_attention_heads * num_batch), num_embedding_size_per_head, 1)
                .to(model.config.torch_dtype)
                .to(model.device),
                torch.zeros(int(num_attention_heads * num_batch), 1, num_embedding_size_per_head)
                .to(model.config.torch_dtype)
                .to(model.device),
            )
            for _ in range(num_block_layers)
        )
    else:
        past_key_values = tuple(
            (
                torch.zeros(num_batch, num_attention_heads, 1, num_embedding_size_per_head)
                .to(model.config.torch_dtype)
                .to(model.device),
                torch.zeros(num_batch, num_attention_heads, 1, num_embedding_size_per_head)
                .to(model.config.torch_dtype)
                .to(model.device),
            )
            for _ in range(num_block_layers)
        )

    dummy_input["attention_mask"] = torch.cat(
        [
            torch.zeros(dummy_input["attention_mask"].shape[0], 1).to(dummy_input["attention_mask"].dtype),
            dummy_input["attention_mask"],
        ],
        -1,
    )

    if model.config.use_cache:
        jit_inputs = (
            dummy_input["input_ids"].to(model.device),
            past_key_values,
            dummy_input["attention_mask"].to(model.device),
        )
    else:
        jit_inputs = (
            dummy_input["input_ids"].to(model.device),
            dummy_input["attention_mask"].to(model.device),
        )

    return jit_inputs


class StopWordsCriteria(StoppingCriteria):
    def __init__(self, tokenizer, stop_words, stream_callback):
        self._tokenizer = tokenizer
        self._stop_words = stop_words
        self._partial_result = ''
        self._stream_buffer = ''
        self._stream_callback = stream_callback

    def __call__(self, input_ids: torch.LongTensor, scores: torch.FloatTensor, **kwargs) -> bool:
        first = not self._partial_result
        text = self._tokenizer.decode(input_ids[0, -1])
        self._partial_result += text
        for stop_word in self._stop_words:
            if stop_word in self._partial_result:
                return True
        if self._stream_callback:
            if first:
                text = text.lstrip()
            # buffer tokens if the partial result ends with a prefix of a stop word, e.g. "<hu"
            for stop_word in self._stop_words:
                for i in range(1, len(stop_word)):
                    if self._partial_result.endswith(stop_word[0:i]):
                        self._stream_buffer += text
                        return False
            self._stream_callback(self._stream_buffer + text)
            self._stream_buffer = ''
        return False


class ChatModel:
    human_id = "<human>"
    bot_id = "<bot>"

    def __init__(self, model_name, gpu_id, max_memory, load_in_8bit, no_gpu, jit):
        if not no_gpu:
            device = torch.device('cuda', gpu_id)
        else:
            device = torch.device('cpu')

        quantization_config = BitsAndBytesConfig(
            load_in_8bit=load_in_8bit, 
            llm_int8_enable_fp32_cpu_offload=True,
        )   # config to load in 8-bit if load_in_8bit
        
        if max_memory == {}:
            device_map="auto"

        else:
            config = AutoConfig.from_pretrained(model_name)
            # load empty weights
            with init_empty_weights():
                model_from_conf = AutoModelForCausalLM.from_config(config)
            model_from_conf.tie_weights()
            
            # correct dtype for cpu/gpu
            if no_gpu:
                dtype = "bfloat16"
            else:
                dtype = "float16"
                
            #create a device_map from max_memory
            device_map = infer_auto_device_map(
                model_from_conf,
                max_memory=max_memory,
                no_split_module_classes=["GPTNeoXLayer"],
                dtype=dtype,
            )
        
        # correct dtype for cpu/gpu
        if no_gpu:
            torch_dtype = torch.bfloat16
        else:
            torch_dtype = torch.float16

        self._model = AutoModelForCausalLM.from_pretrained(
            model_name, 
            torch_dtype=torch_dtype, 
            device_map=device_map, 
            offload_folder="offload",
            quantization_config=quantization_config,
        )
        
        self._tokenizer = AutoTokenizer.from_pretrained(model_name)
        
        if jit:
            jit_input_texts = ["jit"]
            jit_inputs = prepare_jit_inputs(jit_input_texts, self._model, self._tokenizer)
            torch._C._jit_set_texpr_fuser_enabled(False)
            model.config.return_dict = False
            traced_model = torch.jit.trace(self._model, jit_inputs, strict=False)
            traced_model = torch.jit.freeze(traced_model.eval())
            traced_model(*jit_inputs)
            traced_model(*jit_inputs)

            model = _ModelFallbackWrapper(traced_model, model)
        
        

    def do_inference(self, prompt, max_new_tokens, do_sample, temperature, top_k, stream_callback=None):
        stop_criteria = StopWordsCriteria(self._tokenizer, [self.human_id], stream_callback)
        inputs = (
            self._tokenizer(prompt, return_tensors='pt')
            .to(self._model.device)
        )
        outputs = self._model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=do_sample,
            temperature=temperature,
            top_k=top_k,
            pad_token_id=self._tokenizer.eos_token_id,
            stopping_criteria=StoppingCriteriaList([stop_criteria]),
        )
        output = self._tokenizer.batch_decode(outputs)[0]

        # remove the context from the output
        output = output[len(prompt):]

        return output


class OpenChatKitShell(cmd.Cmd):
    intro = "Welcome to OpenChatKit shell.   Type /help or /? to list commands.\n"
    prompt = ">>> "

    def __init__(self, gpu_id, model_name_or_path, max_tokens, sample, temperature, top_k, retrieval, max_memory, do_stream, load_in_8bit, no_gpu, jit):
        super().__init__()
        self._gpu_id = int(gpu_id)
        self._model_name_or_path = model_name_or_path
        self._max_tokens = max_tokens
        self._sample = sample
        self._temperature = temperature
        self._top_k = top_k
        self._retrieval = retrieval
        self._max_memory = max_memory
        self._do_stream = do_stream
        self._load_in_8bit = load_in_8bit
        self._no_gpu = no_gpu
        self._jit = jit

    def preloop(self):
        if not self._no_gpu:
            print(f"Loading {self._model_name_or_path} to cuda:{self._gpu_id}...")
        else:
            print(f"Loading {self._model_name_or_path} to cpu...")
        self._model = ChatModel(self._model_name_or_path, self._gpu_id, self._max_memory, self._load_in_8bit, self._no_gpu, self._jit)

        if self._retrieval:
            print(f"Loading retrieval index...")
            self._index = wp.WikipediaIndex()

        self._convo = convo.Conversation(
            self._model.human_id, self._model.bot_id)

    def precmd(self, line):
        if line.startswith('/'):
            return line[1:]
        else:
            return 'say ' + line

    def do_say(self, arg):
        if self._retrieval:
            results = self._index.search(arg)
            if len(results) > 0:
                self._convo.push_context_turn(results[0])

        self._convo.push_human_turn(arg)

        output = self._model.do_inference(
            self._convo.get_raw_prompt(),
            self._max_tokens,
            self._sample,
            self._temperature,
            self._top_k,
            lambda x : print(x, end='', flush=True) if self._do_stream else None,
        )

        self._convo.push_model_response(output)

        print("" if self._do_stream else self._convo.get_last_turn())

    def do_raw_say(self, arg):
        output = self._model.do_inference(
            arg,
            self._max_tokens,
            self._sample,
            self._temperature,
            self._top_k
        )

        print(output)

    def do_raw_prompt(self, arg):
        print(self._convo.get_raw_prompt())

    def do_reset(self, arg):
        self._convo = convo.Conversation(
            self._model.human_id, self._model.bot_id)

    def do_hyperparameters(self, arg):
        print(
            f"Hyperparameters:\n"
            f"  max_tokens: {self._max_tokens}\n"
            f"  sample: {self._sample}\n"
            f"  temperature: {self._temperature}\n"
            f"  top_k: {self._top_k}"
        )

    def do_quit(self, arg):
        return True


def main():
    parser = argparse.ArgumentParser(
        description='test harness for OpenChatKit')

    parser.add_argument(
        '--gpu-id',
        default=0,
        type=int,
        help='the ID of the GPU to run on'
    )
    parser.add_argument(
        '--model',
        default=f"{INFERENCE_DIR}/../huggingface_models/Pythia-Chat-Base-7B",
        help='name/path of the model'
    )
    parser.add_argument(
        '--max-tokens',
        default=128,
        type=int,
        help='the maximum number of tokens to generate'
    )
    parser.add_argument(
        '--sample',
        default=True,
        action='store_true',
        help='indicates whether to sample'
    )
    parser.add_argument(
        '--no-stream',
        action='store_true',
        help='indicates whether to stream tokens'
    )
    parser.add_argument(
        '--temperature',
        default=0.6,
        type=float,
        help='temperature for the LM'
    )
    parser.add_argument(
        '--top-k',
        default=40,
        type=int,
        help='top-k for the LM'
    )
    parser.add_argument(
        '--retrieval',
        default=False,
        action='store_true',
        help='augment queries with context from the retrieval index'
    )
    parser.add_argument(
        '--no-gpu',
        default=False,
        action='store_true',
        help='argument to use cpu'
    )
    parser.add_argument(
        '-g',
        '--gpu-vram',
        action='store',
        help='max VRAM to allocate per GPU',
        nargs='+',
        required=False,
    )
    parser.add_argument(
        '-r',
        '--cpu-ram',
        default=None,
        type=int,
        help='max CPU RAM to allocate',
        required=False
    )
    # `pip install bitsandbytes` to use. No effect when used with -g or -r.
    parser.add_argument(
        '--load-in-8bit',
        default=False,
        action='store_true',
        help='indicates whether to load model in 8 bit'
    )
    parser.add_argument(
        "--jit", type=bool, default=False, help="Whether or not to use jit trace to accelerate inference"
    )
    args = parser.parse_args()
    
    if args.no_gpu and args.cpu_ram == None:
        raise Exception("-r must be passed when using --no-gpu")

    if args.no_gpu and args.load_in_8bit == True:
        raise Exception("--load-in-8bit cannot be passed when using --no-gpu")
    
    max_memory = {}
    # set max_memory dictionary if given
    if args.gpu_vram is not None:
        for i in range(len(args.gpu_vram)):
            # assign CUDA ID as label and XGiB as value
            max_memory[int(args.gpu_vram[i].split(':')[0])] = f"{args.gpu_vram[i].split(':')[1]}GiB"

    if args.cpu_ram is not None:
        # add cpu to max-memory if given
        max_memory['cpu'] = f"{int(args.cpu_ram)}GiB"

    OpenChatKitShell(
        args.gpu_id,
        args.model,
        args.max_tokens,
        args.sample,
        args.temperature,
        args.top_k,
        args.retrieval,
        max_memory,
        not args.no_stream,
        args.load_in_8bit,
        args.no_gpu,
        args.jit,
    ).cmdloop()


if __name__ == '__main__':
    main()
