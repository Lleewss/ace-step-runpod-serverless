"""
ACE-Step 1.5 RunPod Serverless Handler
Properly handles flash_attn incompatibility by patching at the Python import level.
"""

import os
import sys

# =============================================================================
# STEP 1: PATCH FLASH_ATTN BEFORE ANY OTHER IMPORTS
# This MUST be the very first thing that happens
# =============================================================================

def _create_fake_flash_attn_class():
    from types import ModuleType
    
    class FakeFlashAttnModule(ModuleType):
        def __init__(self, name):
            super().__init__(name)
            self.__version__ = "0.0.0"
            self.__file__ = __file__
            self.__path__ = []
            self.__all__ = []
            
        def __getattr__(self, name):
            def _not_available(*args, **kwargs):
                raise ImportError(f"flash_attn.{name} is not available")
            return _not_available
    
    return FakeFlashAttnModule

def patch_flash_attn():
    FakeModule = _create_fake_flash_attn_class()
    
    modules_to_fake = [
        "flash_attn", "flash_attn_2_cuda",
        "flash_attn.flash_attn_interface", "flash_attn.flash_attn_triton",
        "flash_attn.bert_padding", "flash_attn.flash_blocksparse_attention",
        "flash_attn.layers", "flash_attn.layers.patch_embed",
        "flash_attn.layers.rotary", "flash_attn.ops", "flash_attn.ops.triton",
        "flash_attn.modules", "flash_attn.modules.mha",
    ]
    
    for mod_name in modules_to_fake:
        if mod_name not in sys.modules:
            fake = FakeModule(mod_name)
            def _raise_import(*a, **k):
                raise ImportError("flash_attn disabled")
            fake.flash_attn_func = _raise_import
            fake.flash_attn_varlen_func = _raise_import
            fake.flash_attn_qkvpacked_func = _raise_import
            fake.flash_attn_kvpacked_func = _raise_import
            sys.modules[mod_name] = fake
    
    print("[handler.py] flash_attn modules patched")

# Apply the patch IMMEDIATELY
patch_flash_attn()

# Set environment variables
os.environ["ATTN_BACKEND"] = "sdpa"
os.environ["USE_FLASH_ATTN"] = "0"
os.environ["FLASH_ATTENTION_SKIP_CUDA_BUILD"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["PYTHONUNBUFFERED"] = "1"

# Now safe to import other modules
import runpod
import base64
import tempfile
import traceback
import time

print("[handler.py] Starting ACE-Step 1.5 RunPod Serverless Handler")
print(f"[handler.py] Python: {sys.version}")

# Global state - initialized lazily
_handler = None
_llm_handler = None
_initialized = False

def get_handlers():
    global _handler, _llm_handler, _initialized
    
    if _initialized:
        return _handler, _llm_handler
    
    print("[handler.py] Initializing ACE-Step handlers...")
    
    try:
        ace_step_path = "/app/ace-step"
        if os.path.exists(ace_step_path) and ace_step_path not in sys.path:
            sys.path.insert(0, ace_step_path)
            print(f"[handler.py] Added {ace_step_path} to Python path")
        
        if os.path.exists("/app"):
            print(f"[handler.py] Contents of /app: {os.listdir('/app')}")
        
        from acestep.handler import AceStepHandler
        print("[handler.py] Successfully imported AceStepHandler")
        
        _handler = AceStepHandler()
        
        project_root = "/app/ace-step"
        config_path = os.environ.get("ACESTEP_CONFIG_PATH", "acestep-v15-turbo")
        
        print(f"[handler.py] Initializing DiT model: {config_path}")
        status_msg, success = _handler.initialize_service(
            project_root=project_root,
            config_path=config_path,
            device="cuda",
            use_flash_attention=False,
            compile_model=False,
            offload_to_cpu=False,
        )
        
        if not success:
            raise RuntimeError(f"Failed to initialize DiT model: {status_msg}")
        
        print(f"[handler.py] DiT model initialized: {status_msg}")
        
        try:
            from acestep.llm_inference import LLMHandler
            lm_model_path = os.environ.get("ACESTEP_LM_MODEL_PATH", "acestep-5Hz-lm-1.7B")
            
            _llm_handler = LLMHandler()
            llm_status = _llm_handler.initialize_llm(
                project_root=project_root,
                lm_model_path=lm_model_path,
            )
            print(f"[handler.py] LLM initialized: {llm_status}")
        except Exception as e:
            print(f"[handler.py] LLM initialization skipped: {e}")
            _llm_handler = None
        
        _initialized = True
        print("[handler.py] Handlers initialized successfully")
        return _handler, _llm_handler
        
    except Exception as e:
        print(f"[handler.py] ERROR initializing handlers: {e}")
        traceback.print_exc()
        raise

def handler(job):
    start_time = time.time()
    
    try:
        job_input = job.get("input", {})
        
        caption = job_input.get("caption") or job_input.get("tags", "")
        lyrics = job_input.get("lyrics", "[instrumental]")
        duration = job_input.get("duration", 60)
        bpm = job_input.get("bpm")
        key_scale = job_input.get("key_scale", "")
        time_signature = job_input.get("time_signature", "")
        vocal_language = job_input.get("vocal_language", "en")
        thinking = job_input.get("thinking", True)
        inference_steps = job_input.get("inference_steps", 8)
        guidance_scale = job_input.get("guidance_scale", 7.0)
        seed = job_input.get("seed", -1)
        audio_format = job_input.get("audio_format", "mp3")
        
        duration = max(10, min(600, int(duration)))
        
        print(f"[handler] Generating music:")
        print(f"  Caption: {caption[:100]}..." if len(caption) > 100 else f"  Caption: {caption}")
        print(f"  Duration: {duration}s, Thinking: {thinking}")
        
        dit_handler, llm_handler = get_handlers()
        
        from acestep.inference import generate_music, GenerationParams, GenerationConfig
        
        params = GenerationParams(
            caption=caption,
            lyrics=lyrics,
            duration=float(duration),
            bpm=bpm,
            keyscale=key_scale,
            timesignature=time_signature,
            vocal_language=vocal_language,
            thinking=thinking and llm_handler is not None,
            inference_steps=inference_steps,
            guidance_scale=guidance_scale,
            seed=seed if seed != -1 else -1,
        )
        
        config = GenerationConfig(
            batch_size=1,
            use_random_seed=(seed == -1),
            audio_format=audio_format,
        )
        
        output_dir = tempfile.mkdtemp(prefix="acestep_")
        
        result = generate_music(
            dit_handler=dit_handler,
            llm_handler=llm_handler if thinking else None,
            params=params,
            config=config,
            save_dir=output_dir,
        )
        
        if not result.success:
            raise RuntimeError(f"Generation failed: {result.error}")
        
        if not result.audios:
            raise RuntimeError("No audio generated")
        
        audio_info = result.audios[0]
        audio_path = audio_info.get("path")
        
        if not audio_path or not os.path.exists(audio_path):
            audio_tensor = audio_info.get("tensor")
            if audio_tensor is not None:
                import torchaudio
                audio_path = os.path.join(output_dir, f"output.{audio_format}")
                sample_rate = audio_info.get("sample_rate", 48000)
                torchaudio.save(audio_path, audio_tensor, sample_rate)
        
        if not audio_path or not os.path.exists(audio_path):
            raise RuntimeError("Audio file not created")
        
        with open(audio_path, "rb") as f:
            audio_base64 = base64.b64encode(f.read()).decode("utf-8")
        
        generation_time = time.time() - start_time
        file_size = os.path.getsize(audio_path)
        
        print(f"[handler] Generated {file_size} bytes in {generation_time:.2f}s")
        
        try:
            import shutil
            shutil.rmtree(output_dir)
        except:
            pass
        
        return {
            "audio_base64": audio_base64,
            "duration": duration,
            "seed": audio_info.get("params", {}).get("seed", seed),
            "model": "ace-step-1.5",
            "format": audio_format,
            "generation_time": round(generation_time, 2),
        }
        
    except Exception as e:
        error_msg = str(e)
        print(f"[handler] ERROR: {error_msg}")
        traceback.print_exc()
        return {"error": error_msg}

if __name__ == "__main__":
    print("[handler.py] Starting RunPod serverless worker...")
    
    try:
        get_handlers()
        print("[handler.py] Pre-initialization complete")
    except Exception as e:
        print(f"[handler.py] Pre-initialization failed (will retry on first request): {e}")
    
    runpod.serverless.start({"handler": handler})
