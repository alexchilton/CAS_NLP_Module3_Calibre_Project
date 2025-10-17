# calibre_tools/config.py
import os
from pathlib import Path

# Default paths
DEFAULT_CALIBRE_LIBRARY = os.path.expanduser("~/Calibre Library")
DEFAULT_DATA_DIR = os.path.expanduser("~/.calibre_tools")
DEFAULT_EMBEDDING_FILE = os.path.join(DEFAULT_DATA_DIR, "embeddings.pkl")
DEFAULT_METADATA_FILE = os.path.join(DEFAULT_DATA_DIR, "metadata.json")

# Ensure data directory exists
os.makedirs(DEFAULT_DATA_DIR, exist_ok=True)

# Embedding model settings
DEFAULT_MODEL_NAME = "all-MiniLM-L6-v2"

# Device detection: MPS for Mac, CUDA for GPU, CPU as fallback
import platform
import torch

def get_default_device():
    """Detect the best available device for the current platform"""
    try:
        # Check for CUDA (explicit override)
        if os.environ.get("USE_CUDA") == "1" and torch.cuda.is_available():
            return "cuda"

        # Check for MPS on Mac (Apple Silicon)
        if platform.system() == "Darwin" and hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            # MPS is still experimental - test if it actually works
            try:
                # Simple test to verify MPS works
                test_tensor = torch.zeros(1, device="mps")
                return "mps"
            except Exception:
                # MPS failed, fall back to CPU
                print("Warning: MPS detected but not functional, falling back to CPU")
                return "cpu"
    except Exception as e:
        print(f"Warning: Error detecting device: {e}, falling back to CPU")

    return "cpu"

DEFAULT_DEVICE = get_default_device()

# Cache refresh settings
FORCE_REFRESH = os.environ.get("FORCE_REFRESH") == "1"
CACHE_EXPIRY_DAYS = int(os.environ.get("CACHE_EXPIRY_DAYS", "7"))