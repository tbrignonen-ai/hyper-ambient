import torch

print(f"PyTorch version: {torch.__version__}")
print(f"CUDA available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"Device: {torch.cuda.get_device_name()}")
    print(f"CUDA version: {torch.version.cuda}")
else:
    print("Device: CPU only (no NVIDIA GPU detected)")
