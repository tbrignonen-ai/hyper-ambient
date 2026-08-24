"""
MOTHER Core application — main entry point.

Usage:
    python -m src.core.app
"""
import asyncio
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


class MotherCore:
    """Core orchestration engine for MOTHER."""

    def __init__(self):
        self.running = False
        logger.info("MOTHER Core initialized")

    async def start(self):
        """Start the core event loop."""
        self.running = True
        logger.info("MOTHER Core starting...")
        try:
            await self._main_loop()
        except KeyboardInterrupt:
            logger.info("Shutdown requested")
        finally:
            await self.stop()

    async def _main_loop(self):
        """Main event loop (placeholder)."""
        logger.info("Event loop running. Press Ctrl+C to stop.")
        try:
            while self.running:
                # TODO: Integrate EARS, TURN, MOUTH, BRAIN, ACOUSTIC
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            pass

    async def stop(self):
        """Gracefully stop the core."""
        self.running = False
        logger.info("MOTHER Core stopped")


async def main():
    """Entry point."""
    core = MotherCore()
    await core.start()


if __name__ == "__main__":
    asyncio.run(main())
