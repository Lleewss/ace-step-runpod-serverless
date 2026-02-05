# ACE-Step 1.5 RunPod Serverless Worker
# Docker Hub: mayo12/ace-step-1.5-runpod
FROM runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    git-lfs \
    ffmpeg \
    libsndfile1 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && git lfs install

# Install uv for faster package management
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Clone ACE-Step 1.5 repository
RUN git clone https://github.com/ACE-Step/ACE-Step-1.5.git /app/ace-step

WORKDIR /app/ace-step

# Install packaging first (required for flash-attn build)
RUN uv pip install --system packaging wheel setuptools ninja

# Install ACE-Step dependencies (flash-attn may take a while to compile)
# Use --no-build-isolation so flash-attn can find packaging module
RUN uv pip install --system --no-build-isolation -r requirements.txt

# Install additional dependencies for RunPod
RUN uv pip install --system runpod boto3

# Install vllm for fast LLM inference (used by LLMHandler)
RUN uv pip install --system vllm

# Download models during build for faster cold starts
# This downloads both DiT (acestep-v15-turbo) and LM (acestep-5Hz-lm-1.7B) models
RUN uv pip install --system huggingface_hub
RUN python -c "\
from huggingface_hub import snapshot_download; \
snapshot_download('ACE-Step/ACE-Step-v1.5', local_dir='./checkpoints', ignore_patterns=['*.md', '*.txt']); \
print('Models downloaded successfully')"

# Copy our handler
COPY handler.py /app/handler.py

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV HF_HOME=/app/cache
ENV TRANSFORMERS_CACHE=/app/cache


WORKDIR /app

# RunPod serverless entry point
CMD ["python", "-u", "handler.py"]
