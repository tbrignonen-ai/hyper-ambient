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

# Un tour vocal n'execute qu'un outil. `max_iterations` plafonne les allers-
# retours avec le modele, pas le nombre d'appels *dans* un aller-retour :
# Luciole 8B a pose 30+ `tool_calls` en une seule reponse (17 sept).
MAX_TOOL_CALLS_PER_ITERATION = 1
MAX_TOOL_CALLS_PER_TURN = 1

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


def _plafond_atteint(iteration: int, max_iterations: int, executed: int, max_tool_calls: int) -> Optional[str]:
    """Raison d'arret dicible, ou None si on peut encore executer."""
    if iteration == max_iterations - 1:
        return "max_iterations"
    if executed >= max_tool_calls:
        return "max_tool_calls"
    return None


async def run_tool_loop(
    brain,
    prompt: str,
    registry: ToolRegistry,
    gate,
    *,
    system: Optional[str] = None,
    history: Optional[List[Dict[str, Any]]] = None,
    max_iterations: int = 3,
    max_tool_calls: int = MAX_TOOL_CALLS_PER_TURN,
) -> AsyncIterator[Dict[str, Any]]:
    """Stream de chunks BRAIN, outils executes sous permission entre deux tours.

    Un tour n'execute qu'un outil par defaut (`max_tool_calls=1`), et jamais
    plus d'un appel par iteration — meme si le modele en pose trente d'un coup.
    Apres cet unique appel, les schemas ne sont plus renvoyes : le modele doit
    formuler une reponse, pas encherir.
    """
    messages = _build_messages(prompt, system, history)
    schemas = registry.schemas()
    executed = 0

    for iteration in range(max_iterations):
        pending: List[ToolCall] = []
        # Plus d'outils dans la charge utile une fois le plafond atteint :
        # un schema encore declare, et Luciole 8B recommence la tempete.
        tools_this_round = schemas if executed < max_tool_calls else []

        async for chunk in brain.query_streaming(
            prompt,
            system=system,
            history=history,
            messages=messages,
            tools=tools_this_round,
        ):
            if chunk.get("stop_reason") == "tool_calls":
                pending = list(chunk.get("tool_calls") or [])
                continue  # ce chunk ne sort pas : il n'est pas parlable
            yield chunk

        if not pending:
            return

        reason = _plafond_atteint(iteration, max_iterations, executed, max_tool_calls)
        if reason is not None:
            # Le modele redemande un outil alors qu'on s'arrete : on le dit.
            # Un silence serait la pire des sorties.
            yield {
                "delta": MAX_ITERATIONS_MESSAGE,
                "stop_reason": reason,
                "ttft_ms": None,
            }
            return

        to_run = pending[:MAX_TOOL_CALLS_PER_ITERATION]
        if len(pending) > len(to_run):
            logger.warning(
                "tool_loop: %s appels demandes, %s executes (plafond par iteration)",
                len(pending),
                len(to_run),
            )

        # L'historique ne porte que les appels vraiment executes : le protocole
        # exige un message `tool` par `tool_call` de l'assistant.
        messages.append(_assistant_message(to_run))
        for call in to_run:
            yield {"channel": "tool", "tool": call.name, "phase": "call", "delta": ""}
            result, phase = await _execute(call, registry, gate)
            # `content` hors delta : MOUTH ne parle que les deltas non vides.
            # Le tour vocal le recopie dans `_dernier_outils` pour le tour suivant.
            yield {
                "channel": "tool",
                "tool": call.name,
                "phase": phase,
                "delta": "",
                "content": result.content,
            }
            messages.append(result.to_message())
            executed += 1
