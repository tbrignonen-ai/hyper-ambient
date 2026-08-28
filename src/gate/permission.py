"""
GATE: Permission and execution mode control.

Seven modes control how hyper-ambient behaves:
  plan         — Dry-run, show what would happen
  ask          — Prompt before each action
  manual       — User-triggered batch
  auto         — Automatic (default)
  build        — Development/test mode
  troubleshoot — Verbose logging
  yolo         — Minimum checks (dangerous)
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class Gate:
    """Permission control and execution mode."""

    MODES = {"plan", "ask", "manual", "auto", "build", "troubleshoot", "yolo"}

    def __init__(self, mode: str = "auto"):
        """
        Initialize GATE.

        Args:
            mode: execution mode (default: auto)
        """
        if mode not in self.MODES:
            logger.warning(f"Unknown mode {mode}, defaulting to auto")
            mode = "auto"

        self.mode = mode
        logger.info(f"GATE initialized: mode={mode}")

    def can_execute(self, action: str, requires_approval: bool = False) -> bool:
        """
        Check if action can be executed.

        Args:
            action: action name
            requires_approval: whether this action needs explicit approval

        Returns:
            True if action can proceed
        """
        if self.mode == "yolo":
            return True

        if self.mode == "plan":
            logger.info(f"[PLAN] Would execute: {action}")
            return False

        if self.mode == "ask" and requires_approval:
            logger.warning(f"[ASK] Approval required for: {action}")
            # In real implementation, would wait for user input
            return False

        if self.mode in {"auto", "build", "troubleshoot"}:
            return True

        if self.mode == "manual":
            logger.info(f"[MANUAL] Waiting for user trigger: {action}")
            return False

        return False

    def should_log_verbose(self) -> bool:
        """Return True if verbose logging is enabled."""
        return self.mode in {"troubleshoot", "build"}

    def allows_fallback(self) -> bool:
        """Return True if fallback capabilities are allowed."""
        return self.mode not in {"yolo"}

    async def set_mode(self, new_mode: str):
        """
        Change execution mode.

        Args:
            new_mode: new mode to switch to
        """
        if new_mode not in self.MODES:
            logger.error(f"Invalid mode: {new_mode}")
            return

        logger.warning(f"GATE mode changed: {self.mode} → {new_mode}")
        self.mode = new_mode

    def describe(self) -> str:
        """Return description of current mode."""
        descriptions = {
            "plan": "Dry-run mode: show what would happen (no execution)",
            "ask": "Interactive mode: prompt before each action",
            "manual": "Manual mode: user-triggered actions",
            "auto": "Automatic mode: execute without prompts (default)",
            "build": "Development mode: skip some checks, verbose logging",
            "troubleshoot": "Troubleshooting mode: maximum logging and tracing",
            "yolo": "Unrestricted mode: minimum checks (dangerous!)"
        }
        return descriptions.get(self.mode, "Unknown mode")
