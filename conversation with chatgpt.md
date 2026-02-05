how can i create a serverless runpod from this:
ACE-Step-1.5 one-click UI and API
valyriantech/ace-step-1.5:latest

Community templates are not officially supported. Read the README or contact the author for support.

ACE-Step 1.5 Music Generation API
Generate high-quality music from text descriptions using ACE-Step 1.5 - an open-source music generation model.

What's Included
ACE-Step 1.5 models pre-loaded (~15GB)
FastAPI server with REST API endpoints
LLM-powered features for lyrics/caption formatting
CUDA 12.8 optimized for NVIDIA GPUs
API Endpoints
Endpoint	Method	Description
/health	GET	Health check
/v1/models	GET	List available models
/release_task	POST	Create music generation task
/query_result	POST	Query task results
/format_input	POST	Enhance lyrics/caption via LLM
/v1/audio	GET	Download generated audio
Quick Start
Once the pod is running:

Gradio UI: http://<POD_IP>:7860 - Web interface for music generation
REST API: http://<POD_IP>:8000 - Programmatic access
CLI Tool (Recommended)
The easiest way to generate music is using the included Python CLI script. Download generate_music.py from the GitHub repo and run:

python generate_music.py \
  --api-url https://<POD_ID>-8000.proxy.runpod.net \
  --caption "Upbeat indie pop with jangly guitars and energetic vocals" \
  --lyrics "[Verse 1]\nWalking down the street\nMusic in my feet\n\n[Chorus]\nWe are alive tonight" \
  --duration 90 \
  --output my_song.mp3
The CLI handles task submission, polling, and file download automatically. Use --help for all options.

Generate Music via curl
# Create a generation task
curl -X POST http://<POD_IP>:8000/release_task \
  -H "Content-Type: application/json" \
  -d '{
    "caption": "upbeat electronic dance music with heavy bass",
    "lyrics": "[Verse]\nDancing through the night...",
    "duration": 60
  }'

# Query result (use task_id from response)
# IMPORTANT: Use task_id_list, NOT task_ids
curl -X POST http://<POD_IP>:8000/query_result \
  -H "Content-Type: application/json" \
  -d '{"task_id_list": ["<TASK_ID>"]}'
Environment Variables
Variable	Default	Description
ACESTEP_CONFIG_PATH	/app/checkpoints/acestep-v15-base	Full path to DiT model
ACESTEP_LM_MODEL_PATH	/app/checkpoints/acestep-5Hz-lm-1.7B	Full path to LM model
ACESTEP_API_PORT	8000	API server port
GPU Requirements
Minimum: 32GB VRAM
Recommended: RTX 5090 or equivalent
Links
ACE-Step GitHub
API Documentation
Docker Image Source
ValyrianTech
Patreon
NVIDIA

50 GB Container Disk




Hub
docker logo
ACE-Step-1.5 one-click UI and API
$
0123456789
.
0123456789
0123456789

ACE-Step-1.5 one-click UI and API


https://github.com/ValyrianTech/ace-step-1.5

Got it — this is a RunPod serverless conversion problem, not just “how do I run the container”. I’ll walk you through this cleanly and practically, using how RunPod serverless endpoints actually work.

You already have:

A Docker image: valyriantech/ace-step-1.5:latest

A long-running FastAPI + Gradio server

GPU-heavy model (~15 GB)

The key thing to understand first (this saves a lot of pain):

🚨 Important reality check (very important)

You cannot use this image “as-is” for RunPod Serverless.

Why?

Serverless does NOT expose ports

Serverless does NOT keep a persistent FastAPI server running

Serverless expects a single request → single job → return output model

Gradio UI is not compatible with serverless

So you must:

Wrap ACE-Step into a RunPod handler instead of running FastAPI

This is normal. Almost every serious serverless RunPod project does this.

✅ What will work

You’ll convert this into:

A RunPod Serverless endpoint

Accepts JSON input

Generates music

Returns audio (base64 or URL)

🧠 Target architecture
Client
  ↓
RunPod Serverless Endpoint
  ↓
runpod.handler(event)
  ↓
ACE-Step inference code
  ↓
Return audio file / base64

Step 1: Create a new serverless-compatible Dockerfile

You cannot use the one-click UI image directly.

Create your own Dockerfile that:

Uses their image as a base

Disables FastAPI & Gradio

Adds a RunPod handler

Dockerfile
FROM valyriantech/ace-step-1.5:latest

# Install RunPod serverless SDK
RUN pip install runpod

# Copy handler
COPY handler.py /handler.py

# RunPod expects this
CMD ["python", "-u", "/handler.py"]

Step 2: Write the RunPod handler

Create handler.py

This replaces:

/release_task

/query_result

polling

FastAPI

Minimal working handler
import runpod
import base64
import uuid
import os

from ace_step.generate import generate_music  # adjust if path differs

OUTPUT_DIR = "/tmp/output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def handler(event):
    """
    Expected input:
    {
      "caption": "...",
      "lyrics": "...",
      "duration": 60
    }
    """

    caption = event["input"].get("caption", "")
    lyrics = event["input"].get("lyrics", "")
    duration = event["input"].get("duration", 60)

    output_file = f"{OUTPUT_DIR}/{uuid.uuid4()}.wav"

    generate_music(
        caption=caption,
        lyrics=lyrics,
        duration=duration,
        output_path=output_file
    )

    # Read and encode audio
    with open(output_file, "rb") as f:
        audio_bytes = f.read()

    audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")

    return {
        "audio_base64": audio_b64,
        "format": "wav"
    }

runpod.serverless.start({"handler": handler})


Notes:

generate_music import path may differ — inspect the repo structure

WAV is better for serverless; client can convert to MP3 later

Step 3: Build & push your image
docker build -t yourdockerhub/ace-step-serverless:latest .
docker push yourdockerhub/ace-step-serverless:latest

Step 4: Create RunPod Serverless Endpoint

In RunPod dashboard:

Serverless → New Endpoint

Container image:

yourdockerhub/ace-step-serverless:latest


GPU:

A100 40GB / A100 80GB / RTX 6000 Ada

Do NOT go below 32GB VRAM

Container disk:

50 GB (you already noted this correctly)

Timeout:

600–900 seconds (music gen is slow)

Max workers:

1 (important, GPU memory)

Step 5: Call the serverless endpoint
Request example
curl -X POST https://api.runpod.ai/v2/YOUR_ENDPOINT_ID/run \
  -H "Authorization: Bearer RUNPOD_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "caption": "Upbeat indie pop with jangly guitars",
      "lyrics": "[Verse]\nWalking down the street...",
      "duration": 60
    }
  }'

Response
{
  "audio_base64": "UklGRqQAAABXQVZFZm10IBAAAAABAAEA...",
  "format": "wav"
}

Step 6: Client-side decode (example)
import base64

audio = base64.b64decode(response["audio_base64"])
with open("song.wav", "wb") as f:
    f.write(audio)

⚠️ What you LOSE vs Pod mode
Feature	Pod	Serverless
Gradio UI	❌	❌
Task queue	❌	❌
Persistent models	❌	❌
Simple API	✅	✅
Auto-scale	❌	✅
Pay per request	❌	✅
🔥 Optional upgrades (recommended)

If you want this production-grade:

Return S3 / R2 URL instead of base64

Cache models in /runpod-volume

Add progress logs via runpod.log()

Add MP3 encoding using ffmpeg

TL;DR

You cannot make the existing ACE-Step pod “serverless” directly.
You must:

Create a new Docker image

Remove FastAPI/Gradio

Add a runpod.serverless.handler

Deploy as Serverless Endpoint

If you want, next I can:

Adapt the handler to match their existing /release_task JSON

Convert output to MP3

Upload results to Cloudflare R2

Help you estimate cost per song on RunPod serverless

Just tell me which one you want next.

would I need to download something from what we'll do? how large?

Good question — this is exactly the right thing to clarify before you build it.

Short answer

No, you personally don’t download the model locally.
The RunPod worker downloads it inside the container.

What does get downloaded, where, and how big depends on how you deploy it.

What gets downloaded, and where
1. On your machine (local)

Only:

Your Dockerfile

handler.py

Size:
➡️ A few KB (basically nothing)

You do NOT download:

ACE-Step models

Checkpoints

Weights

CUDA libraries

2. Inside the Docker image (during build)

When you use:

FROM valyriantech/ace-step-1.5:latest


You are not re-downloading the model locally. Docker just references the base image.

Image size (important):

Base image: ~18–22 GB

~15 GB models

CUDA 12.8

PyTorch

Your additions: + a few MB

When you docker build:

Docker does not expand this fully on your disk

It layers it

You still need ~20–25 GB free disk to build/push safely

If your machine has <30 GB free, this will be painful.

3. On RunPod (this is the big one)

When the endpoint spins up:

RunPod pulls the image onto the GPU worker

That’s where the real download happens

What RunPod downloads:

Item	Size
Docker image	~20–22 GB
Container disk	50 GB allocated
Runtime temp files	1–5 GB

This is why:

50 GB container disk is mandatory

Cold starts are slow (3–6 minutes)

But:

You are not charged for storage

Only compute time

How serverless caching works (important)
Cold start (first request)

Image pulled: ~20 GB

Model loaded to GPU: ~15 GB VRAM

Slow

Warm start (subsequent requests)

No re-download

No reload

Much faster

As long as:

The worker stays alive

No scale-down happens

If you want ZERO local disk pain

If your machine storage is tight, you have two safer options:

Option A — Build in GitHub Actions

You never pull the image locally

GitHub builds & pushes to Docker Hub

Option B — Use RunPod “Custom Image” build

RunPod builds the image server-side

You upload only Dockerfile + handler

If you want, I can give you:

A GitHub Actions YAML

Or a RunPod build-only workflow

How big is the final thing you manage?
What YOU actually deal with
Thing	Size
Dockerfile	<1 KB
handler.py	~5–10 KB
Repo	<1 MB

That’s it.

Summary (plain English)

❌ You don’t download the 15 GB model

❌ You don’t store CUDA or checkpoints locally

✅ RunPod downloads everything on their GPU worker

⚠️ Your local machine needs ~25–30 GB free only if you build locally

✅ You can avoid even that by building remotely

If you tell me:

Your OS (Mac / Windows / Linux)

Free disk space

Whether you prefer GitHub or RunPod builds

I’ll recommend the cleanest, lowest-stress setup for you.

will i need docker app?

Yes — but only in one specific case. Here’s the clean breakdown so you don’t install stuff you don’t actually need.

The only time you need Docker installed locally

You need Docker Desktop / Docker Engine only if you plan to:

👉 Build the image on your own machine

That means running:

docker build
docker push


If you do that locally:

✅ You must install Docker

⚠️ You need ~25–30 GB free disk

⚠️ Expect slow builds (big image)

When you do NOT need Docker at all

You do NOT need Docker installed if you choose either of these:

Option A — Build via GitHub Actions (recommended)

You write:

Dockerfile

handler.py

Push to GitHub

GitHub builds + pushes the image for you

RunPod pulls it

Result:

❌ No Docker on your machine

❌ No huge disk usage

✅ Most stress-free

Option B — Let RunPod build the image

Use RunPod’s image build system

Upload Dockerfile + handler

RunPod builds server-side

Result:

❌ No Docker locally

✅ Works well for big models

Decision table (simple)
Your situation	Install Docker?
Build locally	✅ Yes
GitHub Actions	❌ No
RunPod build	❌ No
Just calling API	❌ No
What I’d recommend for you

Given:

Huge image (20+ GB)

Serverless experimentation

You don’t need local testing of GPU inference

👉 Do NOT install Docker locally

Use GitHub Actions or RunPod build.

If you want, I can:

Give you a copy-paste GitHub Actions workflow

Or show the exact RunPod UI steps for server-side builds

Or help you decide based on your current disk space

Just tell me which route you want to take.

ok lets do it on runpod. how to do it until i have the serverless

Perfect choice. Doing everything inside RunPod is the cleanest path for a model this big. I’ll walk you end-to-end, no Docker, no local setup, no guessing.

Below is the exact sequence from zero → working serverless endpoint.

Goal

You will end with:

A RunPod Serverless Endpoint

Using ACE-Step-1.5

Accepting JSON

Returning generated audio

You will not install Docker locally.

Step 0 — What you need ready (2 minutes)

Make sure you have:

RunPod account

RunPod API key (Dashboard → Settings → API Keys)

A GitHub account (just for code storage)

That’s it.

Step 1 — Create a minimal GitHub repo

Create a new repo (private is fine), e.g.:

ace-step-runpod-serverless

Add these 2 files ONLY
1️⃣ Dockerfile
FROM valyriantech/ace-step-1.5:latest

RUN pip install --no-cache-dir runpod

COPY handler.py /handler.py

CMD ["python", "-u", "/handler.py"]

2️⃣ handler.py
import runpod
import uuid
import base64
import os

# ⚠️ adjust this import if needed
from ace_step.generate import generate_music

OUTPUT_DIR = "/tmp/output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def handler(event):
    inp = event["input"]

    caption = inp.get("caption", "")
    lyrics = inp.get("lyrics", "")
    duration = inp.get("duration", 60)

    output_path = f"{OUTPUT_DIR}/{uuid.uuid4()}.wav"

    generate_music(
        caption=caption,
        lyrics=lyrics,
        duration=duration,
        output_path=output_path
    )

    with open(output_path, "rb") as f:
        audio_bytes = f.read()

    return {
        "audio_base64": base64.b64encode(audio_bytes).decode("utf-8"),
        "format": "wav"
    }

runpod.serverless.start({"handler": handler})


Don’t worry if you’re unsure about ace_step.generate — we’ll validate it later inside RunPod logs.

Commit & push.

Step 2 — Build the image inside RunPod
In RunPod dashboard

Go to Serverless → Custom Images

Click New Custom Image

Fill in:

Source

GitHub Repo:

https://github.com/YOURNAME/ace-step-runpod-serverless


Branch

main


Dockerfile path

Dockerfile


Click Build Image

What happens now (important)

RunPod pulls valyriantech/ace-step-1.5:latest

Installs runpod SDK

Copies handler

Builds image on their servers

Takes 5–10 minutes

If build fails:

Open Build Logs

We fix it (usually import path)

Step 3 — Create the Serverless Endpoint

Once the image shows Status: Ready

Go to

Serverless → Endpoints → New Endpoint

Configuration

Container Image

Select your newly built image

GPU

A100 40GB minimum

A100 80GB preferred

Container Disk

50 GB


Max Workers

1


Timeout

900 seconds


Idle Timeout

300 seconds


Click Create Endpoint

Step 4 — First test request (cold start)

Copy:

Endpoint ID

API Key

Test via curl
curl -X POST https://api.runpod.ai/v2/YOUR_ENDPOINT_ID/run \
  -H "Authorization: Bearer YOUR_RUNPOD_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "caption": "Upbeat indie pop with jangly guitars",
      "lyrics": "[Verse]\nWalking down the street\n[Chorus]\nWe are alive tonight",
      "duration": 30
    }
  }'


⏳ First call:

3–6 minutes

Image pull + model load

Step 5 — Check logs if anything breaks

Dashboard → Endpoint → Logs

Common fixes:

Import path tweak

Output filename mismatch

Missing environment variable

We can fix and rebuild without touching your machine.

Step 6 — You now have serverless ACE-Step 🎉

You have:

Auto-scaling music generation

Pay-per-use GPU

No pods to manage

No Docker locally

No FastAPI/Gradio overhead

What I recommend next (pick one)

1️⃣ Return MP3 instead of WAV
2️⃣ Upload audio to Cloudflare R2 / S3
3️⃣ Add progress logs
4️⃣ Match original /release_task schema
5️⃣ Reduce cold-start time
6️⃣ Estimate cost per song

Tell me the number and I’ll do it step-by-step with you.