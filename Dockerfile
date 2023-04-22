# Base image
FROM ubuntu:20.04

VOLUME /app

# Set working directory
WORKDIR /app

# Update and install required packages
RUN apt-get update && \
    apt-get install git-lfs wget gcc -y && \
    rm -rf /var/lib/apt/lists/*

# Download and install Miniconda
RUN wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh && \
    bash Miniconda3-latest-Linux-x86_64.sh -b -p /app/conda && \
    rm Miniconda3-latest-Linux-x86_64.sh

ENV PATH=/app/conda/bin:${PATH}

# Create OpenChatKit environment
COPY environment.yml .
RUN conda install mamba -n base -c conda-forge
RUN mamba env create -f environment.yml 

# Copy OpenChatKit code
COPY . .

ENTRYPOINT ["/app/setup.sh"]
