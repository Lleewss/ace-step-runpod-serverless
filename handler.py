"""
ACE-Step 1.5 RunPod Serverless Handler
Generates music using the ACE-Step 1.5 model

Based on the official ACE-Step 1.5 API:
- https://github.com/ace-step/ACE-Step-1.5
- Uses AceStepHandler (DiT) + LLMHandler (5Hz LM) 
- generate_music() function with GenerationParams and GenerationConfig
"""

import runpod
import os
import sys
import base64
import tempfile
import traceback
import shutil

# Add ace-step to path
sys.path.insert(0, '/app/ace-step')

# Global model instances (loaded once, reused across requests)
dit_handler = None
llm_handler = None
is_initialized = False

def load_models():
    """
    Load ACE-Step 1.5 models using the official API.
    
    Uses:
    - AceStepHandler for DiT model (acestep-v15-turbo)
    - LLMHandler for 5Hz language model (acestep-5Hz-lm-1.7B)
    """
    global dit_handler, llm_handler, is_initialized
    
    if is_initialized:
        return dit_handler, llm_handler
    
    print("Loading ACE-Step 1.5 models...")
    
    from acestep.handler import AceStepHandler
    from acestep.llm_inference import LLMHandler
    
    # Initialize DiT handler (turbo model for fast generation)
    dit_handler = AceStepHandler()
    dit_handler.initialize_service(
        project_root="/app/ace-step",
        config_path="acestep-v15-turbo",
        device="cuda"
    )
    print("✓ DiT handler initialized (acestep-v15-turbo)")
    
    # Initialize LLM handler (1.7B model for best quality with thinking mode)
    llm_handler = LLMHandler()
    llm_handler.initialize(
        checkpoint_dir="/app/ace-step/checkpoints",
        lm_model_path="acestep-5Hz-lm-1.7B",
        backend="vllm",  # vllm is faster than PyTorch
        device="cuda"
    )
    print("✓ LLM handler initialized (acestep-5Hz-lm-1.7B)")
    
    is_initialized = True
    print("✅ All models loaded successfully!")
    return dit_handler, llm_handler


def handler(job):
    """
    RunPod serverless handler for ACE-Step 1.5
    
    Input parameters:
    - caption: str - Music description/style tags (e.g., "upbeat pop song with guitar")
    - lyrics: str - Song lyrics with [verse], [chorus], [bridge] tags
    - duration: int - Duration in seconds (10-600, default: 120)
    - bpm: int - Tempo in BPM (30-300, optional - auto-detected if not provided)
    - key_scale: str - Musical key (e.g., "C Major", "Am", optional)
    - vocal_language: str - Language for vocals (en, zh, ja, etc., default: "en")
    - thinking: bool - Enable Chain-of-Thought for better quality (default: True)
    - inference_steps: int - Diffusion steps (1-20, default: 8 for turbo)
    - seed: int - Random seed (-1 for random, default: -1)
    - use_format: bool - Let LM enhance caption/lyrics (default: False)
    - audio_format: str - Output format: mp3, wav, flac (default: "mp3")
    
    Returns:
    - audio_base64: Base64 encoded audio file
    - duration: Actual duration of generated audio
    - seed: Seed used for generation
    - bpm: BPM of generated music
    - key_scale: Key/scale of generated music
    - model: Model identifier
    - format: Audio format
    """
    try:
        job_input = job["input"]
        
        # Extract parameters with sensible defaults
        caption = job_input.get("caption") or job_input.get("tags", "pop, upbeat, energetic")
        lyrics = job_input.get("lyrics", "[instrumental]")
        duration = job_input.get("duration", 120)
        bpm = job_input.get("bpm")  # Optional - LM will auto-detect
        key_scale = job_input.get("key_scale", "")
        vocal_language = job_input.get("vocal_language", "en")
        thinking = job_input.get("thinking", job_input.get("think_mode", True))
        inference_steps = job_input.get("inference_steps", job_input.get("steps", 8))
        seed = job_input.get("seed", -1)
        use_format = job_input.get("use_format", False)
        audio_format = job_input.get("audio_format", job_input.get("format", "mp3"))
        
        # Validate parameters
        duration = max(10, min(600, int(duration)))  # 10s to 10min
        inference_steps = max(1, min(20, int(inference_steps)))  # Turbo: 1-20, recommended 8
        if bpm is not None:
            bpm = max(30, min(300, int(bpm)))
        if audio_format not in ["mp3", "wav", "flac"]:
            audio_format = "mp3"
        
        print(f"🎵 Generating song:")
        print(f"   Duration: {duration}s, Steps: {inference_steps}, Thinking: {thinking}")
        print(f"   Caption: {caption[:100]}...")
        print(f"   Lyrics: {lyrics[:100]}...")
        
        # Load models
        dit, llm = load_models()
        
        # Import generation functions
        from acestep.inference import GenerationParams, GenerationConfig, generate_music
        
        # Create generation parameters
        params = GenerationParams(
            task_type="text2music",
            caption=caption,
            lyrics=lyrics,
            duration=duration,
            bpm=bpm,
            keyscale=key_scale,
            vocal_language=vocal_language,
            inference_steps=inference_steps,
            shift=3.0,  # Recommended for turbo model
            thinking=thinking,
            use_format=use_format,
        )
        
        # Handle seed
        use_random_seed = (seed == -1)
        
        # Create generation config
        config = GenerationConfig(
            batch_size=1,  # Generate 1 audio at a time for serverless
            audio_format=audio_format,
            use_random_seed=use_random_seed,
        )
        
        # If specific seed requested
        if not use_random_seed:
            params.seed = seed
        
        # Create temp directory for output
        save_dir = tempfile.mkdtemp(prefix="acestep_")
        
        try:
            # Generate music using official API
            result = generate_music(dit, llm, params, config, save_dir)
            
            if not result.success:
                raise Exception(f"Generation failed: {result.error if hasattr(result, 'error') else 'Unknown error'}")
            
            # Get the generated audio file
            if not result.audios or len(result.audios) == 0:
                raise Exception("No audio files generated")
            
            audio_info = result.audios[0]
            audio_path = audio_info.get("path")
            actual_seed = audio_info.get("params", {}).get("seed", seed)
            
            if not audio_path or not os.path.exists(audio_path):
                raise Exception(f"Audio file not found at: {audio_path}")
            
            print(f"✓ Audio generated: {audio_path}")
            
            # Read and encode audio
            with open(audio_path, "rb") as f:
                audio_base64 = base64.b64encode(f.read()).decode("utf-8")
            
            # Extract metadata from result if available
            result_bpm = bpm
            result_keyscale = key_scale
            if hasattr(result, 'metas') and result.metas:
                result_bpm = result.metas.get('bpm', bpm)
                result_keyscale = result.metas.get('keyscale', key_scale)
            
            return {
                "audio_base64": audio_base64,
                "duration": duration,
                "seed": actual_seed,
                "bpm": result_bpm,
                "key_scale": result_keyscale,
                "model": "ace-step-1.5-turbo",
                "format": audio_format
            }
            
        finally:
            # Clean up temp directory
            try:
                shutil.rmtree(save_dir)
            except Exception as e:
                print(f"Warning: Failed to clean up temp dir: {e}")
        
    except Exception as e:
        traceback.print_exc()
        return {"error": str(e)}


# For local testing: python handler.py --test
# For RunPod: the entrypoint runs this file directly
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        # Test locally without RunPod
        test_input = {
            "input": {
                "caption": "acoustic pop, romantic ballad, piano, strings, warm, heartfelt, female vocals",
                "lyrics": "[verse]\nFrom the moment that I saw your face\nI knew my heart had found its place\n\n[chorus]\nThis is where our story starts\nYou will always have my heart",
                "duration": 60,
                "bpm": 95,
                "thinking": True,
                "inference_steps": 8
            }
        }
        
        result = handler(test_input)
        if "error" in result:
            print(f"❌ Error: {result['error']}")
        else:
            print(f"✅ Success! Generated {result['duration']}s audio")
            print(f"   Seed: {result['seed']}, BPM: {result['bpm']}, Format: {result['format']}")
            # Save test output
            with open("test_output.mp3", "wb") as f:
                f.write(base64.b64decode(result["audio_base64"]))
            print("Saved to test_output.mp3")
    else:
        # RunPod serverless mode
        runpod.serverless.start({"handler": handler})
