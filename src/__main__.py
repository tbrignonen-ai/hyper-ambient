"""
hyper-ambient — Main entry point.

Usage:
    python -m src
    python -m src.core.app
    python -m src.core.api
"""
import sys
import asyncio
from .core.app import HyperAmbientCore

if __name__ == "__main__":
    core = HyperAmbientCore()
    asyncio.run(core.start())
