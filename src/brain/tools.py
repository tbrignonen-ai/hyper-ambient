"""
BRAIN: types et registre d'outils.

hyper-ambient est une voix avant d'etre un agent. Deux consequences portees par
ce module, et par lui seul :

  - **La troncature vit dans `ToolResult`, pas dans l'outil.** Un resultat de
    4 000 caracteres lu a voix haute est la pire regression possible ; la
    garantie ne doit dependre d'aucun auteur d'outil, donc elle est appliquee au
    passage du type, pas au bon vouloir du handler.
  - **Le `danger` est porte par la `ToolSpec`.** Le site d'appel ne declare pas
    lui-meme s'il a besoin d'une approbation : une porte dont le visiteur
    choisit la serrure ne protege personne.
"""
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional

# Troncature dure d'un resultat d'outil avant retour au modele. ~1200 caracteres,
# c'est un paragraphe : assez pour repondre, trop court pour un monologue.
MAX_TOOL_CONTENT_CHARS = 1200

# Plafond des arguments JSON d'un appel d'outil. Un modele local (Luciole 8B)
# concatene des fragments SSE jusqu'a rendre le JSON illisible et noyer le
# journal ; au-dela de ce plafond on arrete d'accumuler.
MAX_TOOL_ARGUMENTS_CHARS = 800

_TRUNCATION_MARK = " […]"


@dataclass(frozen=True)
class ToolSpec:
    """Un outil declarable au modele et executable par la boucle."""

    name: str
    description: str
    parameters: Dict[str, Any]  # JSON Schema
    danger: str  # "read" | "write" | "exec"
    handler: Callable[..., Awaitable[str]]

    def to_openai_schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


@dataclass(frozen=True)
class ToolCall:
    """Un appel demande par le modele.

    `raw_arguments` est conserve : un modele local rend regulierement du JSON
    invalide, et il faut pouvoir le tracer sans planter.
    """

    id: str
    name: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    raw_arguments: str = ""


@dataclass(frozen=True)
class ToolResult:
    """Le retour d'un outil, tronque a la construction."""

    call_id: str
    name: str
    ok: bool
    content: str = ""
    error: Optional[str] = None

    def __post_init__(self):
        content = self.content or ""
        if len(content) > MAX_TOOL_CONTENT_CHARS:
            keep = MAX_TOOL_CONTENT_CHARS - len(_TRUNCATION_MARK)
            content = content[:keep].rstrip() + _TRUNCATION_MARK
        object.__setattr__(self, "content", content)

    def to_message(self) -> Dict[str, str]:
        return {
            "role": "tool",
            "tool_call_id": self.call_id,
            "content": self.content,
        }


class ToolRegistry:
    """Les outils dont dispose la boucle, et rien d'autre."""

    def __init__(self):
        self._tools: Dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> ToolSpec:
        self._tools[spec.name] = spec
        return spec

    def get(self, name: str) -> Optional[ToolSpec]:
        return self._tools.get(name)

    def schemas(self) -> List[Dict[str, Any]]:
        return [spec.to_openai_schema() for spec in self._tools.values()]

    def danger_of(self, name: str) -> Optional[str]:
        spec = self._tools.get(name)
        return spec.danger if spec else None

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: object) -> bool:
        return name in self._tools
