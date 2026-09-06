"""
BRAIN: les types d'outils eux-memes — ToolSpec, ToolResult, ToolRegistry, et le
sanitizer d'arguments de la boucle.

test_tool_loop.py prouve la boucle, test_tools_web.py prouve Tavily ; ce fichier
prouve le socle commun : la troncature a la construction du resultat (elle ne
doit dependre d'aucun auteur d'outil), la forme du schema OpenAI, et le filtrage
des cles a secret avant d'atteindre la porte et le journal d'audit.
"""
import asyncio
import functools

from src.brain.tools import (
    MAX_TOOL_CONTENT_CHARS,
    ToolRegistry,
    ToolResult,
    ToolSpec,
)
from src.brain.tool_loop import _sanitize


def runs_async(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        return asyncio.run(fn(*args, **kwargs))

    return wrapper


async def _echo(text: str) -> str:
    return text


def _spec(name="echo", danger="read"):
    return ToolSpec(
        name=name,
        description="Renvoie le texte recu.",
        parameters={"type": "object", "properties": {"text": {"type": "string"}}},
        danger=danger,
        handler=_echo,
    )


def test_le_schema_openai_est_complet():
    schema = _spec().to_openai_schema()
    assert schema["type"] == "function"
    fn = schema["function"]
    assert fn["name"] == "echo"
    assert fn["description"]
    assert "text" in fn["parameters"]["properties"]


def test_le_resultat_court_passe_tel_quel():
    r = ToolResult("1", "echo", ok=True, content="bonjour")
    assert r.content == "bonjour"


def test_la_troncature_vit_dans_le_type_pas_dans_loutil():
    """Un handler qui rend 10 000 caracteres ne peut pas imposer un monologue."""
    r = ToolResult("1", "echo", ok=True, content="x" * 10_000)
    assert len(r.content) <= MAX_TOOL_CONTENT_CHARS
    assert r.content.endswith("[…]")


def test_contenu_none_ne_plante_pas():
    r = ToolResult("1", "echo", ok=True, content=None)
    assert r.content == ""


def test_to_message_a_la_forme_attendue_par_les_messages():
    r = ToolResult("call-42", "echo", ok=True, content="salut")
    msg = r.to_message()
    assert msg == {"role": "tool", "tool_call_id": "call-42", "content": "salut"}


def test_le_registre_enregistre_retrouve_et_declare_le_danger():
    registry = ToolRegistry()
    registry.register(_spec("echo", danger="write"))
    assert "echo" in registry
    assert len(registry) == 1
    assert registry.get("echo").danger == "write"
    assert registry.danger_of("echo") == "write"
    assert registry.danger_of("inconnu") is None
    assert registry.get("inconnu") is None


def test_le_dernier_enregistre_remplace_le_precedent():
    registry = ToolRegistry()
    registry.register(_spec("echo", danger="read"))
    registry.register(_spec("echo", danger="exec"))
    assert len(registry) == 1
    assert registry.danger_of("echo") == "exec"


def test_schemas_rend_tous_les_outils():
    registry = ToolRegistry()
    registry.register(_spec("a"))
    registry.register(_spec("b"))
    names = {s["function"]["name"] for s in registry.schemas()}
    assert names == {"a", "b"}


def test_sanitize_retire_toute_cle_qui_sent_le_secret():
    args = {
        "query": "meteo",
        "api_key": "abc",
        "APIKEY": "abc",
        "token": "abc",
        "Authorization": "Bearer abc",
        "password": "abc",
        "client_secret": "abc",
    }
    cleaned = _sanitize(args)
    assert cleaned == {"query": "meteo"}
    assert not any("abc" in str(v) for v in cleaned.values())


def test_sanitize_supporte_none_et_vide():
    assert _sanitize(None) == {}
    assert _sanitize({}) == {}


def test_sanitize_garde_les_cles_innocentes():
    # "keyboard" est filtre aussi : le filtre est grossier (sous-chaine), et
    # c'est voulu — un faux positif cote porte vaut mieux qu'un secret journalise.
    args = {"query": "q", "max_results": 3, "langue": "fr"}
    assert _sanitize(args) == args


@runs_async
async def test_le_handler_recoit_les_arguments_tels_quels():
    """La troncature est au retour, jamais a l'appel : l'outil voit tout."""
    spec = _spec()
    out = await spec.handler(text="y" * 5000)
    assert len(out) == 5000
    r = ToolResult("1", spec.name, ok=True, content=out)
    assert len(r.content) <= MAX_TOOL_CONTENT_CHARS
