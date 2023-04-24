# Base image
FROM ubuntu:20.04

# Set working directory
WORKDIR /app

# Update and install required packages
RUN apt-get update \
    && apt-get install git-lfs wget curl gcc -y \
    && rm -rf /var/lib/apt/lists/*

# Create OpenChatKit code to /app
COPY . .

# install micromamba
# Linux Intel (x86_64):
RUN mkdir /config && cd /config && curl -Ls https://micro.mamba.pm/api/micromamba/linux-64/latest | tar -xvj bin/micromamba
# # Linux ARM64:
# RUN curl -Ls https://micro.mamba.pm/api/micromamba/linux-aarch64/latest | tar -xvj bin/micromamba
# # Linux Power:
# RUN curl -Ls https://micro.mamba.pm/api/micromamba/linux-ppc64le/latest | tar -xvj bin/micromamba
# # macOS Intel (x86_64):
# RUN curl -Ls https://micro.mamba.pm/api/micromamba/osx-64/latest | tar -xvj bin/micromamba
# # macOS Silicon/M1 (ARM64):
# RUN curl -Ls https://micro.mamba.pm/api/micromamba/osx-arm64/latest | tar -xvj bin/micromamba

# setup venv and install bitsandbytes
RUN eval "$(/config/bin/micromamba shell hook -s posix)" && micromamba create -f environment.yml && micromamba clean --all --yes

# OPTIONAL: Install bitsandbytes
RUN eval "$(/config/bin/micromamba shell hook -s posix)" && micromamba activate OpenChatKit && pip install bitsandbytes

# make setup.sh executable if it's not already
RUN chmod +x setup.sh

# run script on start
ENTRYPOINT ["/app/setup.sh"]
