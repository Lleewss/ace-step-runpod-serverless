import { NextRequest, NextResponse } from 'next/server';

const RUNPOD_API_KEY = process.env.RUNPOD_API_KEY;
const RUNPOD_ENDPOINT_ID = process.env.RUNPOD_ENDPOINT_ID;

interface GenerateSongRequest {
  // Required
  caption: string;  // Music description (genre, mood, instruments)
  lyrics: string;   // Lyrics with [verse], [chorus], etc.
  
  // Optional
  duration?: number;        // 10-600 seconds (default: 120)
  bpm?: number;            // 30-300, auto-detected if not provided
  key_scale?: string;      // e.g., "C Major", "Am"
  vocal_language?: string; // en, zh, ja, etc. (default: "en")
  thinking?: boolean;      // Enable CoT for better quality (default: true)
  inference_steps?: number; // 1-20, recommended 8 for turbo
  seed?: number;           // -1 for random (default: -1)
  use_format?: boolean;    // Let LM enhance caption/lyrics
  audio_format?: string;   // mp3, wav, flac (default: "mp3")
  
  // Legacy support (mapped to new API)
  tags?: string;           // Alias for caption
  think_mode?: boolean;    // Alias for thinking
  steps?: number;          // Alias for inference_steps
}

export async function POST(request: NextRequest) {
  try {
    if (!RUNPOD_API_KEY || !RUNPOD_ENDPOINT_ID) {
      return NextResponse.json(
        { error: 'RunPod not configured. Missing API key or endpoint ID.' },
        { status: 500 }
      );
    }

    const body: GenerateSongRequest = await request.json();

    // Support both old (tags) and new (caption) field names
    const caption = body.caption || body.tags;
    
    if (!caption || !body.lyrics) {
      return NextResponse.json(
        { error: 'Caption (or tags) and lyrics are required' },
        { status: 400 }
      );
    }

    // Map legacy field names to new API
    const thinking = body.thinking ?? body.think_mode ?? true;
    const inference_steps = body.inference_steps ?? body.steps ?? 8;

    console.log('Generating song with ACE-Step 1.5 via RunPod:', {
      duration: body.duration || 120,
      thinking,
      inference_steps
    });

    // Call RunPod Serverless API
    const response = await fetch(
      `https://api.runpod.ai/v2/${RUNPOD_ENDPOINT_ID}/runsync`,
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${RUNPOD_API_KEY}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          input: {
            caption,
            lyrics: body.lyrics,
            duration: body.duration || 120,
            bpm: body.bpm,
            key_scale: body.key_scale || '',
            vocal_language: body.vocal_language || 'en',
            thinking,
            inference_steps,
            seed: body.seed ?? -1,
            use_format: body.use_format || false,
            audio_format: body.audio_format || 'mp3'
          }
        })
      }
    );

    const result = await response.json();

    if (!response.ok) {
      console.error('RunPod API error:', result);
      return NextResponse.json(
        { error: result.error || 'Failed to generate song' },
        { status: response.status }
      );
    }

    // Check for RunPod-specific status
    if (result.status === 'FAILED') {
      return NextResponse.json(
        { error: result.error || 'Song generation failed' },
        { status: 500 }
      );
    }

    // Extract output from RunPod response
    const output = result.output;

    if (output?.error) {
      return NextResponse.json(
        { error: output.error },
        { status: 500 }
      );
    }

    if (output?.audio_base64) {
      // Convert base64 to data URL
      const format = output.format || 'mp3';
      const audioDataUrl = `data:audio/${format};base64,${output.audio_base64}`;
      
      return NextResponse.json({
        success: true,
        audioUrl: audioDataUrl,
        duration: output.duration,
        seed: output.seed,
        bpm: output.bpm,
        key_scale: output.key_scale,
        model: output.model || 'ace-step-1.5-turbo',
        format: output.format || 'mp3'
      });
    }

    // If still processing (shouldn't happen with runsync)
    return NextResponse.json({
      success: false,
      status: result.status,
      message: 'Song is being generated...'
    });

  } catch (error) {
    console.error('Generate song error:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
