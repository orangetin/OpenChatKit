#!/bin/bash

DIR=$(cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd)

ARG_0=$1

eval "$(/config/bin/micromamba shell hook -s posix)"
micromamba activate OpenChatKit

POSITIONAL_ARGS=()

if [[ $ARG_0 == 'inference' ]]; then
	shift
	(trap 'kill 0' SIGINT; \
        python /app/inference/bot.py $(echo $@) \
            & \
        wait)

elif [[ $ARG_0 == 'train' ]]; then
	shift

	while [[ $# -gt 0 ]]; do
          case $1 in
            -m|--model)
              MODEL="$2"
              shift # past argument
              shift # past value
              ;;
            -*|--*)
              echo "Unknown option $1"
              exit 1
              ;;
	    *)
	      POSITIONAL_ARGS+=("$1") # save positional arg
	      shift # past argument
	      ;;
          esac
        done

	if [[ $MODEL == 'gpt-neox' ]]; then
		(trap 'kill 0' SIGINT; \
		bash ${DIR}/training/finetune_GPT-NeoXT-Chat-Base-20B.sh \
                    & \
                wait)
	elif [[ $MODEL == 'pythia' ]]; then
		(trap 'kill 0' SIGINT; \
                bash ${DIR}/training/finetune_Pythia-Chat-Base-7B.sh \
                    & \
                wait)
        else
                # default MODEL=pythia
		(trap 'kill 0' SIGINT; \
                bash ${DIR}/training/finetune_Pythia-Chat-Base-7B.sh \
                    & \
                wait)
	fi

elif [[ $ARG_0 == 'prepare' ]]; then
	shift
	echo "Preparing..."

	(trap 'kill 0' SIGINT; \
	wget https://github.com/git-lfs/git-lfs/releases/download/v3.3.0/git-lfs-linux-amd64-v3.3.0.tar.gz \
	    & \
	tar -xvf git-lfs-linux-amd64-v3.3.0.tar.gz \
	    & \
	./git-lfs-3.3.0/install.sh \
	    & \
	git lfs install \
	    & \
	python ${DIR}/data/OIG/prepare.py \
	    & \
	wait)

	while [[ $# -gt 0 ]]; do
	  case $1 in
	    -m|--model)
	      MODEL="$2"
	      shift # past argument
	      shift # past value
	      ;;
	    -*|--*)
	      echo "Unknown option $1"
	      exit 1
	      ;;
	    *)
	      POSITIONAL_ARGS+=("$1") # save positional arg
	      shift # past argument
	      ;;
	  esac
	done

	echo "Preparing model ${MODEL}..."

	if [[ $MODEL == 'gpt-neox' ]]; then
		(trap 'kill 0' SIGINT; \
		python ${DIR}/pretrained/GPT-NeoX-20B/prepare.py \
		    & \
		wait)
	elif [[ $MODEL == 'pythia' ]]; then
		(trap 'kill 0' SIGINT; \
                python ${DIR}/pretrained/Pythia-6.9B-deduped/prepare.py \
                    & \
                wait)
	else
		# default MODEL=pythia
		(trap 'kill 0' SIGINT; \
                python ${DIR}/pretrained/Pythia-6.9B-deduped/prepare.py \
                    & \
                wait)
	fi

	echo "Done"

else
	# defaults to inference
        (trap 'kill 0' SIGINT; \
        python ${DIR}/inference/bot.py $(echo $@) \
            & \
        wait)

fi
