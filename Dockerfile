# Base image
FROM ubuntu:20.04

# Set working directory
WORKDIR /config

# Update and install required packages
RUN apt-get update \
    && apt-get install git-lfs wget curl gcc -y \
    && rm -rf /var/lib/apt/lists/*

# Create OpenChatKit environment
COPY environment.yml .

RUN curl -Ls https://micro.mamba.pm/api/micromamba/linux-64/latest | tar -xvj bin/micromamba
RUN eval "$(./bin/micromamba shell hook -s posix)" && micromamba create -f environment.yml

# Copy OpenChatKit code
COPY setup.sh .

RUN mkdir /app && cd /app && git clone https://github.com/orangetin/OpenChatKit.git

RUN chmod +x setup.sh

RUN echo "df -h"

VOLUME ["/app"]
VOLUME ["/config"]

ENTRYPOINT ["/config/setup.sh"]
