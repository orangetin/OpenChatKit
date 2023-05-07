# OpenChatKit Inference
This directory contains code for OpenChatKit's inference.

## Contents

- [Arguments](#arguments)
- [Hardware requirements](#hardware-requirements-for-inference)
- [Running on multiple GPUs](#running-on-multiple-gpus)
- [Running on specific GPUs](#running-on-specific-gpus)
- [Running on consumer hardware](#running-on-consumer-hardware)
- [Running on Google Colab](#running-on-google-colab) 

## Arguments
- `--gpu-id`: primary GPU device to load inputs onto for inference. Default: `0`
- `--model`: name/path of the model. Default = `../huggingface_models/Pythia-Chat-Base-7B`
- `--max-tokens`: the maximum number of tokens to generate. Default: `128`
- `--sample`: indicates whether to sample. Default: `True`
- `--temperature`: temperature for the LM. Default: `0.6`
- `--top-k`: top-k for the LM. Default: `40`
- `--retrieval`: augment queries with context from the retrieval index. Default `False`
- `-g` `--gpu-vram`: GPU ID and VRAM to allocate to loading the model, separated by a `:` in the format `ID:RAM` where ID is the CUDA ID and RAM is in GiB. `gpu-id` must be present in this list to avoid errors. Accepts multiple values, for example, `-g ID_0:RAM_0 ID_1:RAM_1 ID_N:RAM_N`
- `-r` `--cpu-ram`: CPU RAM overflow allocation for loading the model. Optional, and only used if the model does not fit onto the GPUs given.
- `--load-in-8bit`: load model in 8-bit. Requires `pip install bitsandbytes`. No effect when used with `-g`. 

## Hardware requirements for inference
The Pythia-Chat-Base-7B model requires:

- **18 GB of GPU memory for the base model**

- **9 GB of GPU memory for the 8-bit quantized model**

Used VRAM also goes up by ~100-200 MB per prompt. 

If you'd like to run inference on a GPU with less VRAM than the size of the model, refer to this section on [running on consumer hardware](#running-on-consumer-hardware).

By default, inference uses only CUDA Device 0.

**NOTE: Inference currently requires at least 1x GPU.**

## Running on multiple GPUs
Add the argument 

```-g ID0:MAX_VRAM ID1:MAX_VRAM ID2:MAX_VRAM ...``` 

where IDx is the CUDA ID of the device and MAX_VRAM is the amount of VRAM you'd like to allocate to the device.

For example, if you are running this on 4x 8 GB GPUs and want to distribute the model across all devices, add ```-g 0:4 1:4 2:6 3:6```. In this example, the first two devices get loaded to a max of 4 GiB while the other two are loaded with a max of 6 GiB.

How it works: The model fills up the max available VRAM on the first device passed and then overflows into the next until the whole model is loaded.

**IMPORTANT: This MAX_VRAM is only for loading the model. It does not account for the additional inputs that are added to the device. It is recommended to set the MAX_VRAM to be at least 1 or 2 GiB less than the max available VRAM on each device, and at least 3GiB less than the max available VRAM on the primary device (set by `gpu-id` default=0).**

**Decrease MAX_VRAM if you run into CUDA OOM. This happens because each input takes up additional space on the device.**

**NOTE: Total MAX_VRAM across all devices must be > size of the model in GB. If not, `bot.py` automatically offloads the rest of the model to RAM and disk. It will use up all available RAM. To allocate a specified amount of RAM: [refer to this section on running on consumer hardware](#running-on-consumer-hardware).**

## Running on specific GPUs
If you have multiple GPUs but would only like to use a specific device(s), [use the same steps as in this section on running on multiple devices](#running-on-multiple-gpus) and only specify the devices you'd like to use. 

Also, if needed, add the argument `--gpu-id ID` where ID is the CUDA ID of the device you'd like to make the primary device. NOTE: The device specified in `--gpu-id` must be present as one of the ID in the argument `-g` to avoid errors.

- **Example #1**: to run inference on devices 2 and 5 with a max of 25 GiB on each, and make device 5 the primary device, add: `--gpu-id 5 -g 2:25 5:25`. In this example, not adding `--gpu-id 5` will give you an error.
- **Example #2**: to run inference on devices 0 and 3 with a max of 10GiB on 0 and 40GiB on 3, with device 0 as the primary device, add: `-g 0:10 3:40`. In this example, `--gpu-id` is not required because device 0 is specified in `-g`.
- **Example #3**: to run inference only on device 1 with a max of 75 GiB, add: `--gpu-id 1 -g 1:75`


## Running on consumer hardware
If you have multiple GPUs [the steps mentioned in this section on running on multiple GPUs](#running-on-multiple-gpus) still apply, unless, any of these apply:
- Running on just 1x GPU with VRAM < size of the model,
- Less combined VRAM across multiple GPUs than the size of the model,
- Running into Out-Of-Memory (OOM) issues

In which case, add the flag `-r CPU_RAM` where CPU_RAM is the maximum amount of RAM you'd like to allocate to loading model. Note: This significantly reduces inference speeds. 

The model will load without specifying `-r`, however, it is not recommended because it will allocate all available RAM to the model. To limit how much RAM the model can use, add `-r`.

If the total VRAM + CPU_RAM < the size of the model in GiB, the rest of the model will be offloaded to a folder "offload" at the root of the directory. Note: This significantly reduces inference speeds.

- Example: `-g 0:3 -r 4` will first load up to 3 GiB of the model into the CUDA device 0, then load up to 4 GiB into RAM, and load the rest into the "offload" directory.

How it works: 
- https://github.com/huggingface/blog/blob/main/accelerate-large-models.md
- https://www.youtube.com/embed/MWCSGj9jEAo

## Running on Google Colab
[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/togethercomputer/OpenChatKit/blob/main/inference/example/example.ipynb)

In the [example notebook](example/example.ipynb), you will find code to run the Pythia-Chat-Base-7B 8-bit quantized model. This is recommended for the free version of Colab. If you'd like to disable quantization, simple remove the `--load-in-8bit` flag from the last cell.

Or, simple click on the "Open In Colab" badge to run the example notebook.

## Running on CPU-only
To run the OpenChatKit without a GPU add the option `--no-gpu`.

Note: -r must be passed with --no-gpu. Some other quirks I noticed when loading the model w/o a gpu: you can't quantize it (must be float32 on cpu); disk offloading does not work.

Example: `python inference/bot.py --model togethercomputer/Pythia-Chat-Base-7B --no-gpu -r 32`
