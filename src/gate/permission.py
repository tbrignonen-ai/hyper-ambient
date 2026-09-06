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
import warnings
from dataclasses import dataclass
from typing import Optional, Callable, Awaitable, Dict, Any

from src.gate.audit import AuditLog

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PermissionRequest:
    tool: str
    arguments: dict
    danger: str  # read|write|exec
    caller: str = "brain.tool_loop"


@dataclass(frozen=True)
class PermissionDecision:
    allowed: bool
    reason: str  # court, francais, PRONONCABLE si False
    mode: str


class Gate:
    """Permission control and execution mode."""

    MODES = {"plan", "ask", "manual", "auto", "build", "troubleshoot", "yolo"}

    # Table des politiques par défaut selon (mode, danger)
    # Danger levels: "read", "write", "exec"
    POLICY_TABLE: Dict[tuple[str, str], tuple[bool, str]] = {
        # auto : exécution normale autorisée pour read, write, exec
        ("auto", "read"): (True, "Lecture autorisée."),
        ("auto", "write"): (True, "Écriture autorisée."),
        ("auto", "exec"): (True, "Exécution autorisée."),

        # plan : simulation uniquement, tout est refusé avec motif explicite
        ("plan", "read"): (False, "Mode simulation actif, lecture non exécutée."),
        ("plan", "write"): (False, "Mode simulation actif, écriture non exécutée."),
        ("plan", "exec"): (False, "Mode simulation actif, exécution non effectuée."),

        # manual : actions en attente de déclenchement manuel par l'utilisateur
        ("manual", "read"): (False, "Action en attente de déclenchement manuel."),
        ("manual", "write"): (False, "Action en attente de déclenchement manuel."),
        ("manual", "exec"): (False, "Action en attente de déclenchement manuel."),

        # build : mode développement
        ("build", "read"): (True, "Lecture autorisée en mode développement."),
        ("build", "write"): (True, "Écriture autorisée en mode développement."),
        ("build", "exec"): (True, "Exécution autorisée en mode développement."),

        # troubleshoot : mode diagnostic
        ("troubleshoot", "read"): (True, "Lecture autorisée en mode diagnostic."),
        ("troubleshoot", "write"): (True, "Écriture autorisée en mode diagnostic."),
        ("troubleshoot", "exec"): (True, "Exécution autorisée en mode diagnostic."),

        # yolo : permissif sans restriction
        ("yolo", "read"): (True, "Lecture autorisée."),
        ("yolo", "write"): (True, "Écriture autorisée."),
        ("yolo", "exec"): (True, "Exécution autorisée."),
    }

    def __init__(
        self,
        mode: str = "auto",
        audit: Optional[AuditLog] = None,
        resolver: Optional[Callable[[PermissionRequest], Awaitable[bool]]] = None,
    ):
        """
        Initialize GATE.

        Args:
            mode: execution mode (default: auto)
            audit: optional AuditLog instance for recording decisions
            resolver: optional async resolver function for 'ask' mode
        """
        if mode not in self.MODES:
            logger.warning(f"Unknown mode {mode}, defaulting to auto")
            mode = "auto"

        self.mode = mode
        self.audit = audit
        self.resolver = resolver
        logger.info(f"GATE initialized: mode={mode}")

    async def check(self, request: PermissionRequest) -> PermissionDecision:
        """
        Check if request is allowed according to current gate mode and tool danger.

        Args:
            request: PermissionRequest containing tool name, arguments, danger level, and caller

        Returns:
            PermissionDecision with allowed bool, French pronounceable reason, and mode
        """
        danger = request.danger

        if self.mode == "ask":
            if self.resolver is not None:
                try:
                    is_approved = await self.resolver(request)
                    if is_approved:
                        decision = PermissionDecision(
                            allowed=True,
                            reason="Action approuvée par l'utilisateur.",
                            mode=self.mode,
                        )
                    else:
                        decision = PermissionDecision(
                            allowed=False,
                            reason="Action refusée par l'utilisateur.",
                            mode=self.mode,
                        )
                except Exception as e:
                    logger.error(f"Error in ask mode resolver: {e}")
                    decision = PermissionDecision(
                        allowed=False,
                        reason="Erreur lors de la demande d'approbation.",
                        mode=self.mode,
                    )
            else:
                decision = PermissionDecision(
                    allowed=False,
                    reason="Aucun moyen de confirmation disponible pour valider cette action.",
                    mode=self.mode,
                )
        else:
            policy = self.POLICY_TABLE.get((self.mode, danger))
            if policy is not None:
                allowed, reason = policy
                decision = PermissionDecision(
                    allowed=allowed,
                    reason=reason,
                    mode=self.mode,
                )
            else:
                decision = PermissionDecision(
                    allowed=False,
                    reason=f"Niveau de danger {danger} non reconnu ou interdit pour le mode {self.mode}.",
                    mode=self.mode,
                )

        if self.audit is not None:
            try:
                result_str = "allowed" if decision.allowed else "denied"
                params = {
                    "tool": request.tool,
                    "arguments": request.arguments,
                    "danger": request.danger,
                    "mode": self.mode,
                    "reason": decision.reason,
                }
                await self.audit.log(
                    action="tool_call",
                    params=params,
                    result=result_str,
                    caller=request.caller,
                )
            except Exception as e:
                logger.error(f"Failed to write to audit log: {e}")

        return decision

    def can_execute(self, action: str, requires_approval: bool = False) -> bool:
        """
        Deprecated: Check if action can be executed.
        Use `check(request)` instead.

        Args:
            action: action name
            requires_approval: whether this action needs explicit approval

        Returns:
            True if action can proceed
        """
        warnings.warn(
            "Gate.can_execute is deprecated and will be removed in a future version. Use Gate.check instead.",
            DeprecationWarning,
            stacklevel=2,
        )
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
            "yolo": "Unrestricted mode: minimum checks (dangerous!)",
        }
        return descriptions.get(self.mode, "Unknown mode")
