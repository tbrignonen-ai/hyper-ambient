"""Les outils dans le tour de parole : ce qui s'entend, et ce qui ne s'entend pas.

Le harnais d'outils existe depuis le sprint du 11 (`ToolRegistry`, `run_tool_loop`,
`ask_codex`, 26 tests verts) mais **aucun code du tour vocal ne l'appelait**. Un
outil qu'on ne peut pas declencher a la voix est racontable, pas demontrable.

Ce fichier pose les trois invariants du branchement, dans l'ordre ou ils cassent :

  1. **Un chunk d'outil n'a pas de `stop_reason`.** `run_tool_loop` emet
     `{"channel": "tool", "tool": ..., "phase": ..., "delta": ""}` — sans cle
     `stop_reason`. Le tour lisait `chunk["stop_reason"]` par indexation directe :
     le premier appel d'outil leve `KeyError`, l'exception est avalee par le
     garde-fou de `_enchainer`, et le tour meurt en silence. Pas de rapport, pas
     de voix, aucune trace a l'oreille.
  2. **Un appel d'outil s'annonce.** Codex met 19 a 36 secondes a repondre.
     Sans annonce, c'est une demi-minute de silence devant le jury — entendu
     comme une panne, pas comme une deliberation.
  3. **L'annonce n'est pas la reponse.** Comme les amorces du routeur, elle part
     dans `amorces` et jamais dans `reply` : recollee, le rapport lirait
     « Je demande a Codex, un instant. Il y a neuf fichiers » comme une phrase.

Les doublures dorment : ni EARS, ni BRAIN, ni MOUTH, ni reseau.
"""
from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

RACINE = Path(__file__).resolve().parents[2]


def _charger_serve_hostagent():
    """Charge le script sans exiger fastapi/uvicorn sur l'hote."""
    if str(RACINE) not in sys.path:
        sys.path.insert(0, str(RACINE))
    # Doublures seulement si le vrai paquet manque (hote). Les poser quand
    # fastapi existe empoisonne `sys.modules` pour toute la session pytest et
    # fait tomber `test_hostagent_*` en cascade — voir la note identique dans
    # `test_amorces_rapport.py`.
    try:  # pragma: no cover - depend de l'environnement, pas du code teste
        import fastapi  # noqa: F401
        import uvicorn  # noqa: F401
    except ImportError:
        for nom in ("fastapi", "fastapi.responses", "fastapi.websockets", "uvicorn"):
            sys.modules.setdefault(nom, MagicMock(name=nom))
    chemin = RACINE / "dev" / "scripts" / "serve_hostagent.py"
    spec = importlib.util.spec_from_file_location("serve_hostagent_outils", chemin)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


serve_hostagent = _charger_serve_hostagent()


# --- 1. L'annonce est une phrase, pas un identifiant --------------------------


def test_annonce_ask_codex_est_prononcable():
    """« ask_codex » ne se prononce pas. La phrase, oui."""
    phrase = serve_hostagent.annonce_outil("ask_codex")
    assert phrase.strip()
    assert "ask_codex" not in phrase
    assert "_" not in phrase
    assert phrase.rstrip().endswith(".")
    assert "Codex" in phrase


def test_annonce_outil_inconnu_reste_prononcable():
    """Un outil sans annonce dediee ne doit pas faire epeler son nom brut."""
    phrase = serve_hostagent.annonce_outil("un_outil_jamais_vu")
    assert phrase.strip()
    assert "un_outil_jamais_vu" not in phrase
    assert "_" not in phrase
    assert phrase.rstrip().endswith(".")


# --- 2. Le registre n'existe que s'il peut servir ------------------------------


def test_registre_vide_sans_jeton_codex(monkeypatch):
    """Sans jeton, le chemin sans outil doit rester exactement celui d'avant.

    Un registre non vide ferait passer chaque tour par `run_tool_loop` pour
    declarer un outil qui ne peut repondre que « Je n'ai pas encore d'acces a
    Codex » — on paierait une boucle pour une phrase d'echec.
    """
    monkeypatch.delenv("CODEX_BRIDGE_TOKEN", raising=False)
    monkeypatch.delenv("CLI_BRIDGE_TOKEN", raising=False)
    monkeypatch.delenv("MUSE_BRIDGE_URL", raising=False)
    monkeypatch.delenv("SEARXNG_URL", raising=False)
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    registre = serve_hostagent.construire_registre(client=object())
    assert [s["function"]["name"] for s in registre.schemas()] == ["calculer"]


def test_registre_expose_web_search_quand_searxng_est_configure(monkeypatch):
    monkeypatch.delenv("CODEX_BRIDGE_TOKEN", raising=False)
    monkeypatch.delenv("CLI_BRIDGE_TOKEN", raising=False)
    monkeypatch.delenv("MUSE_BRIDGE_URL", raising=False)
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.setenv("SEARXNG_URL", "http://host.docker.internal:8080")

    registre = serve_hostagent.construire_registre(client=object())

    assert [s["function"]["name"] for s in registre.schemas()] == [
        "calculer",
        "web_search",
    ]
    assert registre.danger_of("web_search") == "read"


def test_registre_expose_web_search_avec_tavily_seul(monkeypatch):
    monkeypatch.delenv("SEARXNG_URL", raising=False)
    monkeypatch.setenv("TAVILY_API_KEY", "cle-de-test")
    registre = serve_hostagent.construire_registre(client=object())
    assert "web_search" in registre


def test_assert_registre_reflete_exactement_la_configuration(monkeypatch):
    monkeypatch.setenv("CODEX_BRIDGE_TOKEN", "jeton-de-test")
    monkeypatch.setenv("CLI_BRIDGE_TOKEN", "jeton-de-test")
    monkeypatch.setenv("MUSE_BRIDGE_URL", "http://pont:19124")
    monkeypatch.setenv("SEARXNG_URL", "http://searxng:8080")
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    registre = serve_hostagent.construire_registre(client=object())

    assert serve_hostagent.verifier_registre(registre) == {
        "ask_claude",
        "ask_codex",
        "ask_muse",
        "web_search",
        "calculer",
    }


def test_assert_registre_detecte_un_outil_attendu_absent(monkeypatch):
    monkeypatch.setenv("CODEX_BRIDGE_TOKEN", "jeton-de-test")
    with pytest.raises(RuntimeError, match="registre outils incoherent"):
        serve_hostagent.verifier_registre(serve_hostagent.ToolRegistry())


def test_registre_expose_ask_codex_en_lecture(monkeypatch):
    monkeypatch.setenv("CODEX_BRIDGE_TOKEN", "jeton-de-test")
    registre = serve_hostagent.construire_registre(client=object())
    assert "ask_codex" in registre
    assert registre.danger_of("ask_codex") == "read"


def test_annonce_ask_claude_est_prononcable():
    phrase = serve_hostagent.annonce_outil("ask_claude")
    assert phrase.strip()
    assert "ask_claude" not in phrase
    assert "_" not in phrase
    assert phrase.rstrip().endswith(".")
    assert "Claude" in phrase


def test_registre_sans_jeton_cli_n_expose_pas_ask_claude(monkeypatch):
    monkeypatch.setenv("CODEX_BRIDGE_TOKEN", "jeton-de-test")
    monkeypatch.delenv("CLI_BRIDGE_TOKEN", raising=False)
    registre = serve_hostagent.construire_registre(client=object())
    assert "ask_claude" not in registre


def test_registre_expose_ask_claude_quand_le_pont_cli_est_configure(monkeypatch):
    monkeypatch.setenv("CLI_BRIDGE_TOKEN", "jeton-de-test")
    registre = serve_hostagent.construire_registre(client=object())
    assert "ask_claude" in registre
    assert registre.danger_of("ask_claude") == "read"


def test_hermes_n_est_jamais_declare_aujourd_hui(monkeypatch):
    """Le chemin vers Hermes est ecrit, il n'est pas emprunte.

    `hermes.exe` est bien present sur cette machine (mesure de Cursor, qui
    corrige mon inventaire). Rien n'empeche donc techniquement de l'appeler —
    sauf la consigne. L'outil ne doit pas etre declare au modele : un outil
    declare finit toujours par etre appele.
    """
    monkeypatch.setenv("CLI_BRIDGE_TOKEN", "jeton-de-test")
    registre = serve_hostagent.construire_registre(client=object())
    assert "ask_hermes" not in registre


def test_deux_outils_ne_partagent_jamais_la_meme_description(monkeypatch):
    """L'invariant qui decide si le harnais sert a quelque chose.

    Le modele ne dispose que de la description pour choisir son outil. Trois
    agents decrits comme « un agent de code qui lit les fichiers du projet »
    ne lui donnent aucun critere : il tire au sort, et une demonstration qui
    tire au sort rate une fois sur trois. Ce test echoue si deux descriptions
    se ressemblent trop, pas seulement si elles sont identiques.
    """
    monkeypatch.setenv("CODEX_BRIDGE_TOKEN", "jeton-de-test")
    monkeypatch.setenv("CLI_BRIDGE_TOKEN", "jeton-de-test")
    monkeypatch.setenv("MUSE_BRIDGE_URL", "http://pont:19124")
    schemas = serve_hostagent.construire_registre(client=object()).schemas()
    assert len(schemas) >= 3, "ce test ne vaut que si plusieurs outils coexistent"

    def mots(texte):
        return {m for m in texte.lower().replace(",", " ").replace(".", " ").split() if len(m) > 3}

    for i, a in enumerate(schemas):
        for b in schemas[i + 1 :]:
            na, nb = a["function"]["name"], b["function"]["name"]
            ma, mb = mots(a["function"]["description"]), mots(b["function"]["description"])
            recouvrement = len(ma & mb) / len(ma | mb)
            assert recouvrement < 0.6, (
                f"{na} et {nb} se ressemblent a {recouvrement:.0%} : "
                "le modele ne peut pas les departager"
            )


def test_le_client_attend_plus_longtemps_que_le_pont():
    """L'invariant des délais, dans le bon sens.

    Le pont rend une phrase prononçable quand le CLI dépasse son délai
    (« délai dépassé »). Si le client coupait le premier, cette phrase ne
    sortirait jamais et l'utilisateur entendrait le repli générique à la place
    du vrai motif. Le client doit donc être le plus patient des deux.

    Constaté le 13/09 avec l'ancien couple 40 s (pont) / 65 s (client) : le
    pont coupait bien en premier, mais à 40 s — trop tôt pour une analyse
    d'architecture, qui est précisément l'usage de `ask_claude`.
    """
    from native.clibridge.bridge import DEFAULT_TIMEOUT_S as DELAI_PONT_CLI

    assert serve_hostagent.DELAI_OUTIL_CLAUDE_S > DELAI_PONT_CLI

    from native.codexbridge.bridge import DEFAULT_TIMEOUT_S as DELAI_PONT_CODEX

    assert serve_hostagent.DELAI_OUTIL_S > DELAI_PONT_CODEX


def test_annonce_ask_muse_est_prononcable():
    phrase = serve_hostagent.annonce_outil("ask_muse")
    assert phrase.strip()
    assert "ask_muse" not in phrase
    assert "_" not in phrase
    assert phrase.rstrip().endswith(".")
    assert "Muse" in phrase


def test_annonces_de_codex_et_de_muse_sont_distinctes(monkeypatch):
    """Deux agents, deux phrases : « je demande a quelqu'un » deux fois de
    suite ne dirait pas a qui."""
    assert serve_hostagent.annonce_outil("ask_codex") != serve_hostagent.annonce_outil(
        "ask_muse"
    )


def test_registre_sans_url_muse_n_expose_pas_ask_muse(monkeypatch):
    """Brancher un second agent est une decision, pas un effet de bord."""
    monkeypatch.setenv("CODEX_BRIDGE_TOKEN", "jeton-de-test")
    monkeypatch.delenv("MUSE_BRIDGE_URL", raising=False)
    registre = serve_hostagent.construire_registre(client=object())
    assert "ask_muse" not in registre


def test_registre_expose_ask_muse_quand_le_pont_est_configure(monkeypatch):
    """L'URL est lue a l'appel, pas a l'import : le pont Muse se branche sans
    reconstruire l'image ni recreer le conteneur."""
    monkeypatch.setenv("CODEX_BRIDGE_TOKEN", "jeton-de-test")
    monkeypatch.setenv("MUSE_BRIDGE_URL", "http://host.docker.internal:19124")
    registre = serve_hostagent.construire_registre(client=object())
    assert "ask_muse" in registre
    assert registre.danger_of("ask_muse") == "read"
    assert sorted(o["function"]["name"] for o in registre.schemas()) == [
        "ask_codex",
        "ask_muse",
        "calculer",
    ]


# --- 3. Le tour de parole survit a un outil, et l'annonce s'entend -------------


class _ASRDouble:
    async def transcribe(self, audio):
        return {"text": "Demande a Codex ce que fait tool_loop.", "latency_ms": 1.0}


class _MOUTHDouble:
    """Ne synthetise rien : retient ce qu'on lui a demande de dire."""

    sample_rate = serve_hostagent.SAMPLE_RATE

    def __init__(self) -> None:
        self.hors_flux: list[str] = []   # _dire_maintenant : amorces et annonces
        self.flux: list[str] = []        # le flux de tokens de la reponse

    def _bloc(self):
        return {
            "audio": np.zeros(serve_hostagent.FRAME_SAMPLES, dtype=np.float32),
            "sample_rate": self.sample_rate,
        }

    async def load_model(self):
        return True

    async def synthesize(self, phrase):
        self.hors_flux.append(phrase)
        return self._bloc()

    async def synthesize_stream(self, deltas):
        async for delta in deltas:
            self.flux.append(delta)
            yield self._bloc()


class _SocketDouble:
    def __init__(self) -> None:
        self.messages: list[dict] = []

    async def send_json(self, message):
        self.messages.append(message)


class _BrainDouble:
    """Rejoue une sequence de chunks et retient les arguments recus."""

    name = "double"

    def __init__(self, chunks):
        self._chunks = chunks
        self.appels: list[dict] = []

    async def query_streaming(self, prompt, **kw):
        self.appels.append(kw)
        for chunk in self._chunks:
            yield chunk


def _trames_de_parole(secondes: float = 1.0):
    """Du bruit, pas du silence : `est_silence` juge le signal, pas le transcript."""
    n = int(serve_hostagent.SAMPLE_RATE * secondes)
    bruit = np.random.default_rng(20260913).uniform(-0.3, 0.3, n).astype(np.float32)
    return serve_hostagent._trames_depuis_pcm(bruit, [np.zeros(0, dtype=np.float32)])


async def _jouer_tour(pipeline, chunks):
    pipeline.asr = _ASRDouble()
    pipeline.tts = _MOUTHDouble()
    pipeline.brain = _BrainDouble(chunks)
    socket = _SocketDouble()
    await pipeline._enchainer(_trames_de_parole(), socket)
    return socket


def _rapport(socket):
    for message in socket.messages:
        if message.get("type") == "report":
            return message
    return None


# La sequence exacte que rend `run_tool_loop` autour d'un appel : les deux chunks
# d'outil ne portent PAS de cle `stop_reason`.
CHUNKS_AVEC_OUTIL = [
    {"channel": "tool", "tool": "ask_codex", "phase": "call", "delta": ""},
    {"channel": "tool", "tool": "ask_codex", "phase": "result", "delta": ""},
    {"delta": "Il y a neuf fichiers", "stop_reason": None, "ttft_ms": 12.0},
    {"delta": " dans src/brain.", "stop_reason": None, "ttft_ms": None},
    {"delta": "", "stop_reason": "stop", "ttft_ms": None},
]


@pytest.mark.asyncio
async def test_un_chunk_d_outil_ne_tue_pas_le_tour():
    """L'invariant n1 : le tour va jusqu'au rapport malgre les chunks d'outil.

    Sans le correctif, `chunk["stop_reason"]` leve `KeyError`, `_enchainer`
    l'avale, et il ne reste aucun rapport — le symptome exact d'un tour mort.
    """
    socket = await _jouer_tour(serve_hostagent.HostPipeline(), CHUNKS_AVEC_OUTIL)
    rapport = _rapport(socket)
    assert rapport is not None, "aucun rapport : le tour est mort sur le chunk d'outil"
    assert rapport["reply"] == "Il y a neuf fichiers dans src/brain."


@pytest.mark.asyncio
async def test_l_appel_d_outil_s_annonce_a_voix_haute():
    """L'invariant n2 : l'annonce est prononcee, et avant la reponse."""
    pipeline = serve_hostagent.HostPipeline()
    await _jouer_tour(pipeline, CHUNKS_AVEC_OUTIL)
    attendue = serve_hostagent.annonce_outil("ask_codex")
    assert attendue in pipeline.tts.hors_flux, "l'appel d'outil n'a rien dit"
    assert pipeline.tts.hors_flux.index(attendue) == 0


@pytest.mark.asyncio
async def test_l_annonce_ne_s_annonce_qu_a_l_appel():
    """Le resultat et le refus ne parlent pas : une seule annonce par appel."""
    pipeline = serve_hostagent.HostPipeline()
    await _jouer_tour(pipeline, CHUNKS_AVEC_OUTIL)
    attendue = serve_hostagent.annonce_outil("ask_codex")
    assert pipeline.tts.hors_flux.count(attendue) == 1


@pytest.mark.asyncio
async def test_l_annonce_ne_contamine_pas_la_reponse():
    """L'invariant n3 : l'annonce va dans `amorces`, jamais dans `reply`."""
    pipeline = serve_hostagent.HostPipeline()
    socket = await _jouer_tour(pipeline, CHUNKS_AVEC_OUTIL)
    rapport = _rapport(socket)
    attendue = serve_hostagent.annonce_outil("ask_codex")
    assert attendue not in rapport["reply"]
    assert attendue in rapport["amorces"]


@pytest.mark.asyncio
async def test_l_appel_d_outil_se_voit_dans_la_presence():
    """La fenetre doit montrer que hyper-ambient est partie chercher dehors.

    « escalade » est l'etat juste : un appel d'outil sort de la machine. On ne
    cree pas de sixieme etat — `Presence.emettre` refuse tout ce qui n'est pas
    dans les cinq du cahier des charges.
    """
    socket = await _jouer_tour(serve_hostagent.HostPipeline(), CHUNKS_AVEC_OUTIL)
    etats = [m.get("etat") for m in socket.messages if m.get("type") == "state"]
    assert "escalade" in etats


@pytest.mark.asyncio
async def test_la_memoire_ne_retient_pas_l_annonce():
    """Relire « Je demande a Codex » au tour suivant apprendrait a temporiser."""
    pipeline = serve_hostagent.HostPipeline()
    await _jouer_tour(pipeline, CHUNKS_AVEC_OUTIL)
    attendue = serve_hostagent.annonce_outil("ask_codex")
    assert all(attendue not in m["content"] for m in pipeline._historique)


# Le modele parle AVANT d'appeler l'outil (« Je lui demande. »), puis reprend
# apres le resultat. Deux tours de boucle, deux fragments, aucun separateur
# entre eux : c'est la couture qu'il faut recoudre.
CHUNKS_TEXTE_AUTOUR_DE_L_OUTIL = [
    {"delta": "Je lui demande.", "stop_reason": None, "ttft_ms": 10.0},
    {"channel": "tool", "tool": "ask_codex", "phase": "call", "delta": ""},
    {"channel": "tool", "tool": "ask_codex", "phase": "result", "delta": ""},
    {"delta": "Le fichier router.py aiguille.", "stop_reason": None, "ttft_ms": None},
    {"delta": "", "stop_reason": "stop", "ttft_ms": None},
]


@pytest.mark.asyncio
async def test_les_deux_tours_de_boucle_ne_se_recollent_pas_sans_espace():
    """Mesure du 13/09, deux fois sur deux, sur la chaine reelle :

        « Je lui demande.Le fichier router.py joue le role d'aiguilleur... »
        « Je lui pose la question.Muse me repond qu'un modele local... »

    Le modele s'arrete pour appeler l'outil, puis reprend au tour suivant. Les
    deux fragments sont concatenes tels quels. A l'ecrit c'est une coquille ; a
    l'oreille c'est pire, parce que MOUTH decoupe sur la ponctuation et qu'un
    point colle au mot suivant ne fait pas frontiere : les deux phrases sont
    dites d'un seul souffle.
    """
    pipeline = serve_hostagent.HostPipeline()
    socket = await _jouer_tour(pipeline, CHUNKS_TEXTE_AUTOUR_DE_L_OUTIL)
    reply = _rapport(socket)["reply"]
    assert "demande.Le" not in reply, f"couture non recousue : {reply!r}"
    assert reply == "Je lui demande. Le fichier router.py aiguille."


@pytest.mark.asyncio
async def test_mouth_recoit_la_meme_couture_que_le_rapport():
    """Recoudre le rapport sans recoudre la voix ne servirait a rien : c'est la
    voix qu'on entend."""
    pipeline = serve_hostagent.HostPipeline()
    await _jouer_tour(pipeline, CHUNKS_TEXTE_AUTOUR_DE_L_OUTIL)
    assert "demande.Le" not in "".join(pipeline.tts.flux)


@pytest.mark.asyncio
async def test_aucun_espace_ajoute_quand_le_modele_en_met_deja_un():
    """On recoud une couture, on ne double pas les espaces."""
    pipeline = serve_hostagent.HostPipeline()
    socket = await _jouer_tour(
        pipeline,
        [
            {"delta": "Je lui demande.", "stop_reason": None, "ttft_ms": 10.0},
            {"channel": "tool", "tool": "ask_codex", "phase": "call", "delta": ""},
            {"channel": "tool", "tool": "ask_codex", "phase": "result", "delta": ""},
            {"delta": " Le fichier aiguille.", "stop_reason": None, "ttft_ms": None},
            {"delta": "", "stop_reason": "stop", "ttft_ms": None},
        ],
    )
    assert _rapport(socket)["reply"] == "Je lui demande. Le fichier aiguille."


@pytest.mark.asyncio
async def test_aucun_espace_en_tete_quand_l_outil_precede_tout_texte():
    """L'outil appele avant le moindre mot ne doit pas ouvrir la reponse par un
    espace : `reply` serait decale et MOUTH attaquerait sur du vide."""
    pipeline = serve_hostagent.HostPipeline()
    socket = await _jouer_tour(pipeline, CHUNKS_AVEC_OUTIL)
    assert _rapport(socket)["reply"] == "Il y a neuf fichiers dans src/brain."


@pytest.mark.asyncio
async def test_sans_outil_le_tour_reste_celui_d_avant():
    """Non-regression : aucun chunk d'outil, aucune annonce, meme rapport."""
    pipeline = serve_hostagent.HostPipeline()
    socket = await _jouer_tour(
        pipeline,
        [
            {"delta": "Bonsoir.", "stop_reason": None, "ttft_ms": 9.0},
            {"delta": "", "stop_reason": "stop", "ttft_ms": None},
        ],
    )
    rapport = _rapport(socket)
    assert rapport["reply"] == "Bonsoir."
    assert rapport["amorces"] == ""
    assert pipeline.tts.hors_flux == []


@pytest.mark.asyncio
async def test_les_outils_sont_declares_au_modele_quand_le_registre_est_garni(monkeypatch):
    """Le branchement, prouve par ce que le modele recoit.

    Un registre garni doit faire passer le tour par `run_tool_loop`, qui declare
    les schemas au modele. Sans cela, `ask_codex` reste un module que personne
    n'appelle.
    """
    monkeypatch.setenv("CODEX_BRIDGE_TOKEN", "jeton-de-test")
    pipeline = serve_hostagent.HostPipeline()
    pipeline.registre = serve_hostagent.construire_registre(client=object())
    pipeline.porte = serve_hostagent.construire_porte()
    await _jouer_tour(
        pipeline,
        [
            {"delta": "Bonsoir.", "stop_reason": None, "ttft_ms": 9.0},
            {"delta": "", "stop_reason": "stop", "ttft_ms": None},
        ],
    )
    assert pipeline.brain.appels, "le modele n'a pas ete appele"
    outils = pipeline.brain.appels[0].get("tools")
    assert outils, "aucun outil declare au modele : le registre n'est pas branche"
    assert [o["function"]["name"] for o in outils] == ["calculer", "ask_codex"]


class _ASRBonjour:
    async def transcribe(self, audio):
        return {"text": "Bonjour.", "latency_ms": 1.0}


class _ChanOutils:
    def __init__(self, name):
        self.name = name
        self.api_endpoint = f"http://{name}"
        self.calls = []

    async def query_streaming(self, prompt, **kw):
        self.calls.append(kw)
        yield {"delta": "Bonjour.", "stop_reason": None, "ttft_ms": 1.0}
        yield {"delta": "", "stop_reason": "stop", "ttft_ms": None}


@pytest.mark.asyncio
async def test_bonjour_vocal_ne_declare_pas_d_outils_au_reflexe(monkeypatch):
    """Le branchement voix : un salut classé REFLEXE ne voit aucun schéma."""
    from src.brain.router import RouterBrain

    monkeypatch.setenv("CODEX_BRIDGE_TOKEN", "jeton-de-test")
    monkeypatch.setenv("SEARXNG_URL", "http://searxng.local")
    monkeypatch.delenv("CLI_BRIDGE_TOKEN", raising=False)
    monkeypatch.delenv("MUSE_BRIDGE_URL", raising=False)
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)

    pipeline = serve_hostagent.HostPipeline()
    pipeline.registre = serve_hostagent.construire_registre(client=object())
    pipeline.porte = serve_hostagent.construire_porte()
    pipeline.asr = _ASRBonjour()
    pipeline.tts = _MOUTHDouble()
    reflex = _ChanOutils("reflex")
    deep = _ChanOutils("deep")
    router = RouterBrain(reflex, deep, enable_filler=False)

    class _Classify:
        async def post(self, url, json=None):
            class _R:
                def json(inner):
                    return {"content": "REFLEXE"}

            return _R()

    router._client = _Classify()
    pipeline.brain = router
    socket = _SocketDouble()
    await pipeline._enchainer(_trames_de_parole(), socket)

    assert pipeline.registre.schemas(), "le registre doit être garni"
    assert reflex.calls, "le reflexe n'a pas été appelé"
    assert "tools" not in reflex.calls[0]
    assert deep.calls == []
    rapport = _rapport(socket)
    assert rapport is not None
    assert rapport["reply"] == "Bonjour."
    assert pipeline.tts.hors_flux == []


# --- 4. Memoire des resultats d'outils + deux outils par tour -----------------


class _ASRTexte:
    def __init__(self, texte: str) -> None:
        self.texte = texte

    async def transcribe(self, audio):
        return {"text": self.texte, "latency_ms": 1.0}


async def _jouer_tour_texte(pipeline, chunks, texte: str):
    pipeline.asr = _ASRTexte(texte)
    pipeline.tts = _MOUTHDouble()
    pipeline.brain = _BrainDouble(chunks)
    socket = _SocketDouble()
    await pipeline._enchainer(_trames_de_parole(), socket)
    return socket


CHUNKS_AVEC_CONTENU_OUTIL = [
    {"channel": "tool", "tool": "ask_codex", "phase": "call", "delta": ""},
    {
        "channel": "tool",
        "tool": "ask_codex",
        "phase": "result",
        "delta": "",
        "content": "Il y a neuf fichiers dans src/brain.",
    },
    {"delta": "Il y a neuf fichiers", "stop_reason": None, "ttft_ms": 12.0},
    {"delta": " dans src/brain.", "stop_reason": None, "ttft_ms": None},
    {"delta": "", "stop_reason": "stop", "ttft_ms": None},
]


@pytest.mark.asyncio
async def test_le_resultat_outil_est_retenu_hors_annonce():
    """Le tour suivant a besoin du texte Codex, pas de l'amorce TTS."""
    pipeline = serve_hostagent.HostPipeline()
    await _jouer_tour(pipeline, CHUNKS_AVEC_CONTENU_OUTIL)
    attendue = serve_hostagent.annonce_outil("ask_codex")
    assert pipeline._dernier_outils
    assert pipeline._dernier_outils[0]["name"] == "ask_codex"
    assert "neuf fichiers" in pipeline._dernier_outils[0]["content"]
    assert all(attendue not in m["content"] for m in pipeline._historique)
    assert all(attendue not in o["content"] for o in pipeline._dernier_outils)
    assert len(pipeline._historique) <= serve_hostagent.MEMOIRE_MESSAGES


@pytest.mark.asyncio
async def test_le_tour_suivant_injecte_le_resultat_outil_dans_l_historique():
    """Sans ça, le modèle dit « pas de texte Codex » au tour d'après."""
    pipeline = serve_hostagent.HostPipeline()
    await _jouer_tour(pipeline, CHUNKS_AVEC_CONTENU_OUTIL)
    await _jouer_tour_texte(
        pipeline,
        [
            {"delta": "Claude a lu Codex.", "stop_reason": None, "ttft_ms": 8.0},
            {"delta": "", "stop_reason": "stop", "ttft_ms": None},
        ],
        "Demande a Claude de contre-analyser Codex.",
    )
    assert pipeline.brain.appels, "le second tour n'a pas appelé le modèle"
    history = pipeline.brain.appels[0].get("history") or []
    injectes = [
        m["content"]
        for m in history
        if "[résultat outil ask_codex]" in m.get("content", "")
    ]
    assert injectes, f"résultat outil absent de l'historique: {history!r}"
    assert "neuf fichiers" in injectes[0]


@pytest.mark.asyncio
async def test_le_resultat_outil_expire_apres_le_tour_de_suivi():
    """Le resultat aide la reprise immediate, jamais les tours ulterieurs."""
    pipeline = serve_hostagent.HostPipeline()
    await _jouer_tour(pipeline, CHUNKS_AVEC_CONTENU_OUTIL)
    await _jouer_tour_texte(
        pipeline,
        [
            {"delta": "Je poursuis.", "stop_reason": None, "ttft_ms": 8.0},
            {"delta": "", "stop_reason": "stop", "ttft_ms": None},
        ],
        "Continue.",
    )
    await _jouer_tour_texte(
        pipeline,
        [
            {"delta": "Nouveau sujet.", "stop_reason": None, "ttft_ms": 8.0},
            {"delta": "", "stop_reason": "stop", "ttft_ms": None},
        ],
        "Et maintenant ?",
    )

    history = pipeline.brain.appels[0].get("history") or []
    assert not any("[résultat outil ask_codex]" in m.get("content", "") for m in history)
    assert pipeline._dernier_outils == []


@pytest.mark.asyncio
async def test_un_resultat_outil_trop_long_est_tronque():
    trop = "X" * 4000
    pipeline = serve_hostagent.HostPipeline()
    await _jouer_tour(
        pipeline,
        [
            {"channel": "tool", "tool": "ask_codex", "phase": "call", "delta": ""},
            {
                "channel": "tool",
                "tool": "ask_codex",
                "phase": "result",
                "delta": "",
                "content": trop,
            },
            {"delta": "Voila.", "stop_reason": "stop", "ttft_ms": 1.0},
        ],
    )
    from src.brain.tools import MAX_TOOL_CONTENT_CHARS

    assert len(pipeline._dernier_outils[0]["content"]) <= MAX_TOOL_CONTENT_CHARS


@pytest.mark.asyncio
async def test_un_tour_autorise_deux_outils(monkeypatch):
    """Codex puis Claude dans le même tour : max_tool_calls=2, un appel par itération."""
    captured = {}

    async def spy(*args, **kwargs):
        captured["max_tool_calls"] = kwargs.get("max_tool_calls")
        if False:
            yield {}

    monkeypatch.setattr(serve_hostagent, "run_tool_loop", spy)
    pipeline = serve_hostagent.HostPipeline()
    pipeline.registre = serve_hostagent.construire_registre(client=None)
    pipeline.porte = serve_hostagent.construire_porte()
    await _jouer_tour(
        pipeline,
        [
            {"delta": "Bonsoir.", "stop_reason": None, "ttft_ms": 9.0},
            {"delta": "", "stop_reason": "stop", "ttft_ms": None},
        ],
    )
    assert captured.get("max_tool_calls") == 2
    from src.brain.tool_loop import MAX_TOOL_CALLS_PER_ITERATION

    assert MAX_TOOL_CALLS_PER_ITERATION == 1
    assert serve_hostagent.MEMOIRE_MESSAGES == 12
