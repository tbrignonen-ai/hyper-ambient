"""
Test configuration and fixtures for hyper-ambient.
"""
import pytest
import sys
from pathlib import Path

# Add workspace to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


@pytest.fixture
def audio_device_available():
    """Check if audio device is available (e.g., /dev/snd in container)."""
    import os
    return os.path.exists("/dev/snd") or sys.platform == "win32"


@pytest.fixture
def gpu_available():
    """Check if CUDA GPU is available."""
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        return False


@pytest.fixture
def models_dir():
    """Return path to models directory."""
    return Path(__file__).parent.parent.parent / "models"
