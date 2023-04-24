# Base image
FROM ubuntu:20.04

# Set working directory
WORKDIR /config

# Update and install required packages
RUN apt-get update \
    && apt-get install git-lfs wget curl gcc -y \
    && rm -rf /var/lib/apt/lists/*

# Create OpenChatKit code to /app
COPY . /app


# install micromamba

# Linux Intel (x86_64):
RUN curl -Ls https://micro.mamba.pm/api/micromamba/linux-64/latest | tar -xvj bin/micromamba
# # Linux ARM64:
# RUN curl -Ls https://micro.mamba.pm/api/micromamba/linux-aarch64/latest | tar -xvj bin/micromamba
# # Linux Power:
# RUN curl -Ls https://micro.mamba.pm/api/micromamba/linux-ppc64le/latest | tar -xvj bin/micromamba
# # macOS Intel (x86_64):
# RUN curl -Ls https://micro.mamba.pm/api/micromamba/osx-64/latest | tar -xvj bin/micromamba
# # macOS Silicon/M1 (ARM64):
# RUN curl -Ls https://micro.mamba.pm/api/micromamba/osx-arm64/latest | tar -xvj bin/micromamba


# setup venv
RUN eval "$(./bin/micromamba shell hook -s posix)" && micromamba create -f /app/environment.yml

# make setup.sh executable if it's not already
RUN chmod +x /app/setup.sh

# run script on start
ENTRYPOINT ["/app/setup.sh"]
