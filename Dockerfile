# ACE-Step 1.5 RunPod Serverless Worker
# Use valyriantech's pre-built image (has all deps + models working)
FROM valyriantech/ace-step-1.5:latest

# Remove broken flash-attn and use SDPA fallback
RUN pip uninstall -y flash-attn || true

# Install RunPod SDK
RUN pip install --no-cache-dir runpod

# Copy our serverless handler
COPY handler.py /app/handler.py

# Set environment variables to disable flash-attn and use SDPA
ENV PYTHONUNBUFFERED=1
ENV ATTN_BACKEND=sdpa
ENV USE_FLASH_ATTN=0
ENV DIFFUSERS_ATTN_IMPLEMENTATION=sdpa

WORKDIR /app

# RunPod serverless entry point (overrides the default FastAPI server)
CMD ["python", "-u", "handler.py"]
