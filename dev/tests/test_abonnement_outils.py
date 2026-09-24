"""Le cerveau abonnement confie des tâches aux harnais (séance du 24/09).

« Teste tes accès à Internet par Claude puis par Codex, en reprenant la
session déjà ouverte avec chacun » : GPT-6-Luna, sans outils, répondait
lui-même qu'il n'avait pas accès aux sessions. Le modèle écrit désormais une
ligne ``<<ask_claude: …>>`` ; MOTHER la retire de la voix et en fait un vrai
appel d'outil — donc un mandat, dans la session courante du harnais.
"""
import asyncio

from src.brain.abonnement import ExtracteurOutils, SubscriptionBrain, consignes_outils


def test_texte_sans_marqueur_passe_tel_quel():
    e = ExtracteurOutils({"ask_claude"})
    assert e.pousser("Bonjour, ") + e.pousser("ça va ?") + e.finir() == "Bonjour, ça va ?"
    assert e.appels == []


def test_marqueur_coupe_entre_deux_morceaux_est_retire_et_note():
    e = ExtracteurOutils({"ask_claude", "ask_codex"})
    dit = "".join([
        e.pousser("Je demande. <"),
        e.pousser("<ask_claude: teste ton accès "),
        e.pousser("à Internet>>\n<<ask_codex: teste"),
        e.pousser(" ton accès à Internet>>"),
        e.finir(),
    ])
    assert dit.strip() == "Je demande."
    assert [(a.name, a.arguments["question"]) for a in e.appels] == [
        ("ask_claude", "teste ton accès à Internet"),
        ("ask_codex", "teste ton accès à Internet"),
    ]


def test_un_chevron_seul_n_est_pas_un_marqueur():
    e = ExtracteurOutils({"ask_claude"})
    assert e.pousser("3 <") + e.pousser(" 4") + e.finir() == "3 < 4"


def test_outil_inconnu_ignore():
    e = ExtracteurOutils({"ask_claude"})
    e.pousser("<<rm_rf: />>")
    assert e.appels == [] and e.finir() == ""


def test_consignes_decrivent_seulement_les_harnais():
    outils = [
        {"type": "function", "function": {"name": "ask_claude", "description": "Claude Code"}},
        {"type": "function", "function": {"name": "calculer", "description": "Calcul"}},
    ]
    texte = consignes_outils(outils)
    assert "<<ask_claude:" in texte
    assert "calculer" not in texte


class _Reponse:
    status_code = 200

    def __init__(self, lignes):
        self.lignes = lignes

    async def aiter_lines(self):
        for ligne in self.lignes:
            yield ligne

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _Client:
    def __init__(self, lignes):
        self.lignes = lignes
        self.corps = None

    def stream(self, methode, url, headers=None, json=None):
        self.corps = json
        return _Reponse(self.lignes)


def test_le_cerveau_rend_un_appel_d_outil_et_rien_a_prononcer():
    import json as _json

    cerveau = SubscriptionBrain(bridge_url="http://h/ask", token="t")
    cerveau.client = _Client([
        _json.dumps({"delta": "<<ask_claude: teste ton accès à Internet"}),
        _json.dumps({"delta": ">>"}),
        _json.dumps({"done": True}),
    ])
    outils = [{"type": "function", "function": {"name": "ask_claude", "description": "Claude"}}]

    async def scenario():
        return [c async for c in cerveau.query_streaming("q", system="SYS", tools=outils)]

    morceaux = asyncio.run(scenario())
    assert "".join(c.get("delta") or "" for c in morceaux) == ""
    (appel,) = morceaux[-1]["tool_calls"]
    assert morceaux[-1]["stop_reason"] == "tool_calls"
    assert (appel.name, appel.arguments) == ("ask_claude", {"question": "teste ton accès à Internet"})
    systeme = cerveau.client.corps["messages"][0]["content"]
    assert systeme.startswith("SYS") and "<<ask_claude:" in systeme


def test_les_consignes_restent_quand_le_tour_n_a_plus_d_outils():
    """Changer de consignes ouvrirait un nouveau fil côté pont (plus lent)."""
    import json as _json

    cerveau = SubscriptionBrain(bridge_url="http://h/ask", token="t")
    outils = [{"type": "function", "function": {"name": "ask_codex", "description": "Codex"}}]
    for liste in (outils, []):
        cerveau.client = _Client([_json.dumps({"delta": "ok"})])

        async def scenario():
            return [c async for c in cerveau.query_streaming("q", system="SYS", tools=liste)]

        asyncio.run(scenario())
        assert "<<ask_codex:" in cerveau.client.corps["messages"][0]["content"]


# -- boucle d'outils : plusieurs harnais, et arrêt après le dépôt -------------

class _CerveauDeuxMarqueurs:
    def __init__(self):
        self.appels = 0

    async def query_streaming(self, prompt, **kw):
        from src.brain.tools import ToolCall

        self.appels += 1
        yield {"delta": "", "stop_reason": "tool_calls", "ttft_ms": None, "tool_calls": [
            ToolCall(id="a", name="ask_claude", arguments={"question": "teste Internet"}),
            ToolCall(id="b", name="ask_codex", arguments={"question": "teste Internet"}),
        ]}


def _registre(recus):
    from src.brain.mandat import RegistreMandats
    from src.brain.tools import ToolRegistry, ToolSpec

    registre = ToolRegistry()
    for outil, nom in (("ask_claude", "Claude"), ("ask_codex", "Codex")):
        class Mandat:
            registre_mandats = RegistreMandats()

            async def __call__(self, question, _nom=nom):
                recus.append((_nom, question))
                return f"Je demande à {_nom}."

        registre.register(ToolSpec(name=outil, description=nom,
                                   parameters={"type": "object"}, danger="read", handler=Mandat()))
    return registre


def test_le_modele_confie_aux_deux_harnais_sans_etre_rappele():
    from dev.scripts import serve_hostagent
    from src.gate.permission import Gate

    recus = []
    cerveau = _CerveauDeuxMarqueurs()

    async def scenario():
        deltas = []
        async for chunk in serve_hostagent.flux_cerveau(
            cerveau, "Vérifie l'accès Internet de chacun des deux.", _registre(recus),
            Gate(mode="auto"), [],
        ):
            if chunk.get("delta"):
                deltas.append(chunk["delta"])
        return deltas

    deltas = asyncio.run(scenario())
    assert [nom for nom, _ in recus] == ["Claude", "Codex"]
    assert cerveau.appels == 1
    assert "Je demande à Claude." in deltas and "Je demande à Codex." in deltas


class _CerveauQuiRepondPuisConfie:
    """Abonnement : répond à sa part, puis confie le reste aux harnais."""

    class deep:
        supporte_outils = False

    async def query_streaming(self, prompt, **kw):
        from src.brain.tools import ToolCall

        yield {"delta": "Oui, j'ai accès au web.", "stop_reason": None, "ttft_ms": 1.0}
        yield {"delta": "", "stop_reason": "tool_calls", "ttft_ms": None, "tool_calls": [
            ToolCall(id="a", name="ask_claude", arguments={"question": "teste Internet"}),
        ]}


def test_abonnement_la_reponse_du_modele_avant_le_depot_est_gardee():
    from dev.scripts import serve_hostagent
    from src.gate.permission import Gate

    recus = []

    async def scenario():
        deltas = []
        async for chunk in serve_hostagent.flux_cerveau(
            _CerveauQuiRepondPuisConfie(),
            "As-tu accès à Internet, et vérifie aussi celui de Claude.",
            _registre(recus), Gate(mode="auto"), [],
        ):
            if chunk.get("delta"):
                deltas.append(chunk["delta"])
        return deltas

    deltas = asyncio.run(scenario())
    assert deltas == ["Oui, j'ai accès au web.", "Je demande à Claude."]
