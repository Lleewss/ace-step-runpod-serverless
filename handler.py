"""
ACE-Step 1.5 RunPod Serverless Handler
Based on valyriantech/ace-step-1.5:latest image
"""

import os
import sys
from types import ModuleType
from unittest.mock import MagicMock
import importlib.abc
import importlib.machinery

# CRITICAL: Set environment variables BEFORE importing anything else
os.environ['ATTN_BACKEND'] = 'sdpa'
os.environ['USE_FLASH_ATTN'] = '0'
os.environ['DIFFUSERS_ATTN_IMPLEMENTATION'] = 'sdpa'
os.environ['TORCH_SDPA_ENABLED'] = '1'

# ============================================================
# BLOCK FLASH_ATTN AT THE IMPORT SYSTEM LEVEL
# ============================================================

class FlashAttnBlocker(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    """Intercept any attempt to import flash_attn and return a fake module"""
    
    BLOCKED_MODULES = frozenset([
        'flash_attn',
        'flash_attn_2_cuda', 
        'flash_attn.flash_attn_interface',
        'flash_attn.flash_attn_triton',
        'flash_attn.bert_padding',
        'flash_attn.flash_blocksparse_attention',
    ])
    
    def find_module(self, fullname, path=None):
        if fullname in self.BLOCKED_MODULES or fullname.startswith('flash_attn'):
            return self
        return None
    
    def find_spec(self, fullname, path, target=None):
        if fullname in self.BLOCKED_MODULES or fullname.startswith('flash_attn'):
            return importlib.machinery.ModuleSpec(fullname, self)
        return None
    
    def load_module(self, fullname):
        if fullname in sys.modules:
            return sys.modules[fullname]
        
        # Create a fake module with MagicMock attributes
        fake = MagicMock()
        fake.__name__ = fullname
        fake.__loader__ = self
        fake.__package__ = fullname.rsplit('.', 1)[0] if '.' in fullname else fullname
        fake.__path__ = []
        fake.__file__ = None
        
        # Make sure common functions exist but raise when called
        def _disabled(*args, **kwargs):
            raise ImportError(f"{fullname} is disabled - using SDPA fallback")
        
        fake.flash_attn_func = _disabled
        fake.flash_attn_varlen_func = _disabled
        fake.flash_attn_qkvpacked_func = _disabled
        
        sys.modules[fullname] = fake
        return fake
    
    def create_module(self, spec):
        return None
    
    def exec_module(self, module):
        pass

# Install the blocker as the FIRST meta path finder
# This ensures it intercepts flash_attn before Python searches the filesystem
sys.meta_path.insert(0, FlashAttnBlocker())

# Also pre-populate sys.modules to prevent any race conditions
for mod_name in FlashAttnBlocker.BLOCKED_MODULES:
    if mod_name not in sys.modules:
        fake = MagicMock()
        fake.__name__ = mod_name
        sys.modules[mod_name] = fake

# Block xformers too if needed
sys.modules['xformers'] = MagicMock()
sys.modules['xformers.ops'] = MagicMock()

print("[handler.py] Flash-attn blocker installed, using SDPA fallback")

import runpod
import base64
import tempfile
import traceback
import subprocess
import glob

# Global state
is_initialized = False
ace_step_module = None

def find_ace_step():
    """Find ACE-Step installation in the container"""
    possible_paths = [
        '/app',
        '/app/ace-step',
        '/app/ACE-Step-1.5',
        '/workspace',
        '/opt/ace-step',
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            # Look for key files
            for root, dirs, files in os.walk(path):
                if 'inference.py' in files or 'generate.py' in files:
                    print(f"Found ACE-Step at: {root}")
                    return root
                if 'acestep' in dirs:
                    print(f"Found acestep module at: {path}")
                    return path
    
    return None

def load_models():
    """Load ACE-Step models - auto-discover module structure"""
    global is_initialized, ace_step_module
    
    if is_initialized:
        return True
    
    print("Discovering ACE-Step installation...")
    
    # Find ace-step path
    ace_path = find_ace_step()
    if ace_path:
        sys.path.insert(0, ace_path)
        print(f"Added {ace_path} to Python path")
    
    # Try different import patterns
    try:
        # Pattern 1: acestep.pipeline (common structure)
        from acestep.pipeline import ACEStepPipeline
        print("✓ Found acestep.pipeline.ACEStepPipeline")
        ace_step_module = "pipeline"
        is_initialized = True
        return True
    except ImportError as e:
        print(f"Pipeline import failed: {e}")
    
    try:
        # Pattern 2: acestep.inference
        from acestep import inference
        print("✓ Found acestep.inference")
        ace_step_module = "inference"
        is_initialized = True
        return True
    except ImportError as e:
        print(f"Inference import failed: {e}")
    
    try:
        # Pattern 3: Direct import
        import acestep
        print(f"✓ Found acestep: {dir(acestep)}")
        ace_step_module = "acestep"
        is_initialized = True
        return True
    except ImportError as e:
        print(f"acestep import failed: {e}")
    
    # Pattern 4: Check for CLI script
    cli_paths = glob.glob('/app/**/generate*.py', recursive=True)
    if cli_paths:
        print(f"Found CLI scripts: {cli_paths}")
        ace_step_module = "cli"
        is_initialized = True
        return True
    
    print("❌ Could not find ACE-Step module")
    return False


def generate_with_cli(caption, lyrics, duration, output_path, **kwargs):
    """Generate music using CLI if available"""
    cli_script = glob.glob('/app/**/generate*.py', recursive=True)
    if not cli_script:
        raise Exception("No CLI script found")
    
    cmd = [
        'python', cli_script[0],
        '--caption', caption,
        '--lyrics', lyrics,
        '--duration', str(duration),
        '--output', output_path
    ]
    
    if kwargs.get('bpm'):
        cmd.extend(['--bpm', str(kwargs['bpm'])])
    if kwargs.get('seed') and kwargs['seed'] != -1:
        cmd.extend(['--seed', str(kwargs['seed'])])
    
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    
    if result.returncode != 0:
        raise Exception(f"CLI failed: {result.stderr}")
    
    return output_path


def generate_with_pipeline(caption, lyrics, duration, output_path, **kwargs):
    """Generate music using ACEStepPipeline"""
    from acestep.pipeline import ACEStepPipeline
    
    pipeline = ACEStepPipeline.from_pretrained(
        "/app/checkpoints" if os.path.exists("/app/checkpoints") else "ACE-Step/ACE-Step-v1.5"
    )
    pipeline = pipeline.to("cuda")
    
    audio = pipeline(
        prompt=caption,
        lyrics=lyrics,
        duration=duration,
        num_inference_steps=kwargs.get('inference_steps', 8),
    )
    
    # Save audio
    import soundfile as sf
    sf.write(output_path, audio.squeeze().cpu().numpy(), 44100)
    
    return output_path


def handler(job):
    """RunPod serverless handler"""
    try:
        job_input = job["input"]
        
        caption = job_input.get("caption") or job_input.get("tags", "pop, upbeat, energetic")
        lyrics = job_input.get("lyrics", "[instrumental]")
        duration = min(600, max(10, int(job_input.get("duration", 120))))
        audio_format = job_input.get("audio_format", "mp3")
        
        kwargs = {
            'bpm': job_input.get('bpm'),
            'seed': job_input.get('seed', -1),
            'inference_steps': job_input.get('inference_steps', 8),
            'thinking': job_input.get('thinking', True),
        }
        
        print(f"🎵 Generating: duration={duration}s, format={audio_format}")
        print(f"   Caption: {caption[:100]}...")
        
        # Load models
        if not load_models():
            raise Exception("Failed to load ACE-Step models")
        
        # Create temp output
        output_dir = tempfile.mkdtemp(prefix="acestep_")
        output_path = os.path.join(output_dir, f"output.{audio_format}")
        
        try:
            # Generate based on discovered module
            if ace_step_module == "pipeline":
                generate_with_pipeline(caption, lyrics, duration, output_path, **kwargs)
            elif ace_step_module == "cli":
                generate_with_cli(caption, lyrics, duration, output_path, **kwargs)
            else:
                # Try pipeline first, then CLI
                try:
                    generate_with_pipeline(caption, lyrics, duration, output_path, **kwargs)
                except Exception as e:
                    print(f"Pipeline failed, trying CLI: {e}")
                    generate_with_cli(caption, lyrics, duration, output_path, **kwargs)
            
            # Check if file was created
            if not os.path.exists(output_path):
                # Try wav extension
                output_path = os.path.join(output_dir, "output.wav")
                if not os.path.exists(output_path):
                    raise Exception(f"Output file not created")
            
            # Read and encode
            with open(output_path, "rb") as f:
                audio_base64 = base64.b64encode(f.read()).decode("utf-8")
            
            print(f"✅ Generated {os.path.getsize(output_path)} bytes")
            
            return {
                "audio_base64": audio_base64,
                "duration": duration,
                "seed": kwargs.get('seed', -1),
                "model": "ace-step-1.5",
                "format": audio_format
            }
            
        finally:
            # Cleanup
            try:
                import shutil
                shutil.rmtree(output_dir)
            except:
                pass
                
    except Exception as e:
        traceback.print_exc()
        return {"error": str(e)}


# Start RunPod serverless worker
if __name__ == "__main__":
    print("Starting ACE-Step 1.5 RunPod Serverless Worker...")
    print(f"Python path: {sys.path}")
    print(f"Working directory: {os.getcwd()}")
    print(f"Contents of /app: {os.listdir('/app') if os.path.exists('/app') else 'N/A'}")
    runpod.serverless.start({"handler": handler})
