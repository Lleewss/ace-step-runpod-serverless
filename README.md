# ACE-Step 1.5 RunPod Serverless Deployment Guide

Deploy production-quality AI music generation using ACE-Step 1.5 on RunPod Serverless.

**Key Features:**
- ACE-Step 1.5 Turbo model (<2s generation on A100)
- 1.7B parameter Language Model for "Thinking" mode (best quality)
- Scale-to-zero pricing (pay only when generating)
- <4GB VRAM requirement

---

## Quick Start

### Step 1: Build the Docker Image

```bash
cd /Users/lew/Documents/Headless/vinylcreatives/Temporary/ace-step-1.5-runpod

# Build the image (takes ~20-30 minutes due to model download)
docker build -t ace-step-1.5-runpod .
```

### Step 2: Push to Docker Hub

```bash
# Login to Docker Hub
docker login

# Tag the image for mayo12
docker tag ace-step-1.5-runpod mayo12/ace-step-1.5-runpod:latest

# Push to Docker Hub
docker push mayo12/ace-step-1.5-runpod:latest
```

### Step 3: Deploy on RunPod

1. Go to [RunPod Serverless Console](https://www.runpod.io/console/serverless)
2. Click **"New Endpoint"**
3. Select **"Docker Image"**
4. Enter image: `mayo12/ace-step-1.5-runpod:latest`
5. Configure:
   - **GPU**: RTX 4090 or A100 (24GB+ VRAM recommended)
   - **Min Workers**: 0 (scale to zero when idle)
   - **Max Workers**: 3-5 (based on expected load)
   - **Idle Timeout**: 5 seconds
   - **Execution Timeout**: 300 seconds (5 min for long songs)
6. Click **"Deploy"**

### Step 4: Get Your Credentials

After deployment:
- **Endpoint ID**: Found in the endpoint URL (e.g., `abc123xyz`)
- **API Key**: Found in RunPod Settings → API Keys
- **Full URL**: `https://api.runpod.ai/v2/{ENDPOINT_ID}/runsync`

---

## API Reference

### Environment Variables

Add to your `.env`:
```
RUNPOD_API_KEY=your_runpod_api_key
RUNPOD_ENDPOINT_ID=your_endpoint_id
```

### Request Parameters

| Parameter | Type | Default | Range/Options | Description |
|-----------|------|---------|---------------|-------------|
| `caption` | string | required | - | Music description (genre, mood, instruments) |
| `lyrics` | string | `"[instrumental]"` | - | Lyrics with `[verse]`, `[chorus]`, `[bridge]` tags |
| `duration` | int | `120` | 10-600 | Song length in seconds |
| `bpm` | int | auto | 30-300 | Tempo (auto-detected if not provided) |
| `key_scale` | string | auto | e.g., "C Major", "Am" | Musical key |
| `vocal_language` | string | `"en"` | en, zh, ja, etc. | Language for vocals |
| `thinking` | bool | `true` | - | Enable Chain-of-Thought (recommended for quality) |
| `inference_steps` | int | `8` | 1-20 | Diffusion steps (8 is optimal for turbo) |
| `seed` | int | `-1` | -1 or positive | Random seed (-1 = random) |
| `use_format` | bool | `false` | - | Let LM enhance caption/lyrics |
| `audio_format` | string | `"mp3"` | mp3, wav, flac | Output format |

### Request Example

```json
{
  "input": {
    "caption": "upbeat pop song with acoustic guitar, warm vocals, catchy melody",
    "lyrics": "[verse]\nWalking down the street today\nFeeling like I found my way\n\n[chorus]\nThis is where I want to be\nFinally feeling free",
    "duration": 120,
    "bpm": 110,
    "vocal_language": "en",
    "thinking": true,
    "inference_steps": 8
  }
}
```

### Response Example

```json
{
  "audio_base64": "base64_encoded_audio_data...",
  "duration": 120,
  "seed": 847291,
  "bpm": 110,
  "key_scale": "G Major",
  "model": "ace-step-1.5-turbo",
  "format": "mp3"
}
```

### cURL Example

```bash
curl -X POST "https://api.runpod.ai/v2/YOUR_ENDPOINT_ID/runsync" \
  -H "Authorization: Bearer YOUR_RUNPOD_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "caption": "romantic acoustic ballad, piano, strings, emotional, 80 BPM",
      "lyrics": "[verse]\nFrom the moment that I saw you\nI knew you were the one",
      "duration": 90,
      "thinking": true
    }
  }'
```

---

## Pricing Estimate

| GPU | Cost/hr | Generation Time (60s song) | Cost/Song |
|-----|---------|---------------------------|-----------|
| RTX 3090 | ~$0.30 | ~8-12s | ~$0.001 |
| RTX 4090 | ~$0.50 | ~4-6s | ~$0.0008 |
| A100 40GB | ~$1.00 | ~2-3s | ~$0.0008 |

**Note**: With scale-to-zero, you only pay when generating! No idle costs.

---

## Quality Tips

1. **Always use `thinking: true`** - This uses the 1.7B LM to generate audio codes, resulting in significantly better quality music.

2. **Be descriptive with caption** - Include genre, mood, instruments, tempo, vocal style:
   ```
   "indie folk, warm acoustic guitar, soft female vocals, nostalgic, intimate, 95 BPM"
   ```

3. **Structure lyrics properly** - Use section tags:
   ```
   [intro]
   
   [verse]
   Your verse lyrics here
   
   [chorus]
   Your chorus lyrics here
   
   [bridge]
   Bridge lyrics
   
   [outro]
   ```

4. **For instrumentals** - Use `[instrumental]` as lyrics and describe the vibe in caption.

5. **Duration recommendations**:
   - Short (30-60s): Quick demos, jingles
   - Medium (90-120s): Full song structure
   - Long (180-240s): Extended arrangements

---

## Troubleshooting

### Cold Start (~30-60s)
First request after idle loads the model. This is normal. Subsequent requests are fast (<10s).

### Out of Memory (OOM)
- Reduce `duration` to ≤180s
- Upgrade to RTX 4090 or A100
- Set `thinking: false` (reduces quality)

### Timeout Errors
- Increase RunPod execution timeout to 600s for songs >3 minutes

### Poor Quality Output
- Make sure `thinking: true` is enabled
- Be more descriptive in `caption`
- Try different `seed` values
- Increase `inference_steps` to 12-16

---

## Integration with VinylCreatives

Once deployed, update your `.env`:
```
RUNPOD_API_KEY=rp_xxxxxxxxxxxxxx
RUNPOD_ENDPOINT_ID=abc123xyz
```

Then update `/app/api/generate-song/route.ts` to use the RunPod endpoint instead of Replicate.

---

## Files

- `Dockerfile` - Container build instructions
- `handler.py` - RunPod serverless handler using official ACE-Step 1.5 API
- `route-runpod.ts` - Next.js API route example for integration
- `README.md` - This file
