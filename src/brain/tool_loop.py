"""
BRAIN: la boucle d'appel d'outil, sous permission.

Neutre sur le harnais : `run_tool_loop` prend un `brain`, un `registry` et un
`gate`, et rend un flux de chunks. Elle est appelable depuis la boucle vocale
comme depuis un agent externe — ce choix-la n'est pas tranche ici.

Trois regles vocales gouvernent le fichier :

  - **Rien de non parlable ne sort en `delta`.** Les emissions de trace portent
    `delta=""` par construction ; MOUTH ne parle que les deltas non vides, donc
    elles ne peuvent pas devenir du son.
  - **Un refus se dit.** Le motif rendu par la porte est repousse au modele
    comme resultat d'outil : il apprend le refus et le formule lui-meme, au lieu
    du silence.
  - **La boucle n'ecrit aucune amorce.** Les fillers appartiennent a router.py.
"""
import json
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, AsyncIterator, Dict, List, Optional

from src.brain.tools import ToolCall, ToolRegistry, ToolResult

if TYPE_CHECKING:  # pragma: no cover - contrat partage, ecrit cote GATE
    from src.gate.permission import PermissionRequest as _PermissionRequest

logger = logging.getLogger(__name__)

try:  # le vrai type si GATE est la, un double structurel sinon
    from src.gate.permission import PermissionRequest  # type: ignore
except Exception:  # pragma: no cover - chemin sans GATE

    @dataclass(frozen=True)
    class PermissionRequest:  # type: ignore[no-redef]
        tool: str
        arguments: Dict[str, Any] = field(default_factory=dict)
        danger: str = "read"
        caller: str = "brain.tool_loop"


try:
    from src.mouth.normalize import VOICE_SYSTEM_PROMPT as DEFAULT_SYSTEM
except Exception:  # pragma: no cover
    DEFAULT_SYSTEM = ""

CALLER = "brain.tool_loop"

# Arret propre plutot qu'un modele qui rappelle le meme outil indefiniment.
MAX_ITERATIONS_MESSAGE = (
    "Je n'arrive pas a aboutir avec mes outils. Je m'arrete la."
)

# Cles jamais transmises a la porte ni journalisees : la requete de permission
# est lue par un humain et ecrite dans un journal d'audit.
_SECRET_KEYS = ("api_key", "apikey", "key", "token", "secret", "password", "authorization")


def _sanitize(arguments: Dict[str, Any]) -> Dict[str, Any]:
    return {
        k: v
        for k, v in (arguments or {}).items()
        if not any(marker in k.lower() for marker in _SECRET_KEYS)
    }


def _build_messages(prompt, system, history) -> List[Dict[str, Any]]:
    """Meme construction que `_payload` sans `messages` — la boucle passe par
    `messages=` des le premier tour, donc la charge utile doit coincider."""
    messages: List[Dict[str, Any]] = [{"role": "system", "content": system or DEFAULT_SYSTEM}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": prompt})
    return messages


def _assistant_message(calls: List[ToolCall]) -> Dict[str, Any]:
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {
                "id": call.id,
                "type": "function",
                "function": {"name": call.name, "arguments": call.raw_arguments},
            }
            for call in calls
        ],
    }


async def _execute(call: ToolCall, registry: ToolRegistry, gate) -> tuple:
    """Rend (ToolResult, phase) — phase vaut "result" ou "denied"."""
    spec = registry.get(call.name)
    if spec is None:
        return (
            ToolResult(call.id, call.name, ok=False,
                       content=f"L'outil {call.name} n'existe pas.", error="unknown_tool"),
            "result",
        )

    # `not {}` est vrai : un objet JSON vide (outil sans parametre) ne doit
    # pas etre confondu avec du JSON illisible. On reparse le brut seulement
    # quand finalize n'a rien pu peupler.
    arguments = dict(call.arguments or {})
    if call.raw_arguments.strip() and not arguments:
        try:
            parsed = json.loads(call.raw_arguments)
        except json.JSONDecodeError:
            parsed = None
        if not isinstance(parsed, dict):
            return (
                ToolResult(call.id, call.name, ok=False,
                           content="Je n'ai pas compris les parametres de cet outil.",
                           error="bad_arguments"),
                "result",
            )
        arguments = parsed

    request = PermissionRequest(
        tool=call.name,
        arguments=_sanitize(arguments),
        danger=registry.danger_of(call.name) or "exec",
        caller=CALLER,
    )
    decision = await gate.check(request)
    if not getattr(decision, "allowed", False):
        reason = getattr(decision, "reason", "") or "Je n'ai pas l'autorisation de faire cela."
        return (
            ToolResult(call.id, call.name, ok=False, content=reason, error="denied"),
            "denied",
        )

    try:
        content = await spec.handler(**arguments)
    except Exception as exc:  # l'erreur brute ne remonte pas au modele
        logger.warning(f"outil {call.name} en echec: {exc}")
        return (
            ToolResult(call.id, call.name, ok=False,
                       content=f"L'outil {call.name} n'a pas repondu.", error=str(exc)),
            "result",
        )

    if not isinstance(content, str):
        content = json.dumps(content, ensure_ascii=False, default=str)
    return (ToolResult(call.id, call.name, ok=True, content=content), "result")


async def run_tool_loop(
    brain,
    prompt: str,
    registry: ToolRegistry,
    gate,
    *,
    system: Optional[str] = None,
    history: Optional[List[Dict[str, Any]]] = None,
    max_iterations: int = 3,
) -> AsyncIterator[Dict[str, Any]]:
    """Stream de chunks BRAIN, outils executes sous permission entre deux tours."""
    messages = _build_messages(prompt, system, history)
    schemas = registry.schemas()

    for iteration in range(max_iterations):
        pending: List[ToolCall] = []

        async for chunk in brain.query_streaming(
            prompt,
            system=system,
            history=history,
            messages=messages,
            tools=schemas,
        ):
            if chunk.get("stop_reason") == "tool_calls":
                pending = list(chunk.get("tool_calls") or [])
                continue  # ce chunk ne sort pas : il n'est pas parlable
            yield chunk

        if not pending:
            return

        if iteration == max_iterations - 1:
            # Le modele redemande un outil au dernier tour : on s'arrete, mais
            # on le dit. Un silence serait la pire des sorties.
            yield {
                "delta": MAX_ITERATIONS_MESSAGE,
                "stop_reason": "max_iterations",
                "ttft_ms": None,
            }
            return

        messages.append(_assistant_message(pending))
        for call in pending:
            yield {"channel": "tool", "tool": call.name, "phase": "call", "delta": ""}
            result, phase = await _execute(call, registry, gate)
            yield {"channel": "tool", "tool": call.name, "phase": phase, "delta": ""}
            messages.append(result.to_message())
