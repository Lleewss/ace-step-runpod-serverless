# ACE-Step 1.5 RunPod Serverless Worker
# Use valyriantech's pre-built image (has all deps + models working)
FROM valyriantech/ace-step-1.5:latest

# Install RunPod SDK
RUN pip install --no-cache-dir runpod

# Copy our serverless handler
COPY handler.py /app/handler.py

# Set environment variables
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# RunPod serverless entry point (overrides the default FastAPI server)
CMD ["python", "-u", "handler.py"]
CMD ["python", "-u", "handler.py"]
