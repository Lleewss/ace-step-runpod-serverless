# ACE-Step 1.5 RunPod Serverless Worker
# Use valyriantech's pre-built image (has all deps + models working)
FROM valyriantech/ace-step-1.5:latest

# Completely remove flash-attn to prevent any loading attempts
# The handler.py will provide fake modules that gracefully fail
RUN pip uninstall -y flash-attn flash_attn || true && \
    rm -rf /usr/local/lib/python*/dist-packages/flash_attn* && \
    rm -rf /usr/local/lib/python*/site-packages/flash_attn* && \
    find / -name "flash_attn*.so" -delete 2>/dev/null || true

# Install RunPod SDK
RUN pip install --no-cache-dir runpod

# Copy our serverless handler
COPY handler.py /app/handler.py

# Set environment variables to disable flash-attn and use SDPA
ENV PYTHONUNBUFFERED=1
ENV ATTN_BACKEND=sdpa
ENV USE_FLASH_ATTN=0
ENV DIFFUSERS_ATTN_IMPLEMENTATION=sdpa
ENV HF_HOME=/app/cache

WORKDIR /app

# RunPod serverless entry point (overrides the default FastAPI server)
CMD ["python", "-u", "handler.py"]
