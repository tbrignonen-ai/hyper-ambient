"""Mandat asynchrone : l'appel harnais sort du tour de parole.

Aucun reseau. `analyser` / `envelopper` sont monkeypatchés : le module voisin
`contrat_harnais` peut encore etre en cours d'ecriture.
"""
from __future__ import annotations

import asyncio
import functools
import importlib.util
import sys
import time
import types
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

RACINE = Path(__file__).resolve().parents[2]


def runs_async(fn):
    """Execute un test asynchrone sans dependre de pytest-asyncio."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        return asyncio.run(fn(*args, **kwargs))

    return wrapper


def _assurer_contrat_harnais() -> None:
    """Import reel s'il existe ; sinon un double le temps que le voisin atterrisse."""
    nom = "src.brain.contrat_harnais"
    try:
        __import__(nom)
        return
    except ImportError:
        pass
    if nom in sys.modules:
        return
    mod = types.ModuleType(nom)

    class ReponseHarnais:
        def __init__(
            self,
            verdict="fait",
            resume_voix="",
            detail_voix="",
            resultat_complet="",
            conforme=True,
        ):
            self.verdict = verdict
            self.resume_voix = resume_voix
            self.detail_voix = detail_voix
            self.resultat_complet = resultat_complet
            self.conforme = conforme

    def envelopper(question: str) -> str:
        return f"[contrat]\n{question}"

    def analyser(texte: str) -> ReponseHarnais:
        return ReponseHarnais(
            resume_voix=(texte or "")[:220],
            resultat_complet=texte or "",
            conforme=True,
        )

    mod.ReponseHarnais = ReponseHarnais
    mod.envelopper = envelopper
    mod.analyser = analyser
    sys.modules[nom] = mod


_assurer_contrat_harnais()

from src.brain.mandat import (  # noqa: E402
    DELAI_EXPIRATION_S,
    DELAI_RAPPEL_S,
    MAX_MANDATS_EN_COURS,
    Mandat,
    PleinMandats,
    RegistreMandats,
    confier,
    extraire_harnais,
    extraire_sujet,
    phrase_accuse,
    phrase_arrivee,
    phrase_plein,
    phrase_rappel,
)
from src.i18n import t  # noqa: E402


def _reponse(**kwargs):
    from src.brain.contrat_harnais import ReponseHarnais

    valeurs = {
        "verdict": "fait",
        "resume_voix": "Le fichier est propre.",
        "detail_voix": "Detail long qu'on ne lit jamais.",
        "resultat_complet": "X" * 4000,
        "conforme": True,
    }
    valeurs.update(kwargs)
    return ReponseHarnais(**valeurs)


# --- dataclass + registre -----------------------------------------------------


def test_mandat_porte_les_champs_du_brief():
    m = Mandat(
        identifiant="abc",
        harnais="Codex",
        question="relire transport.py",
        sujet="relire transport.py",
        depose_a=1.0,
        etat="en_cours",
        reponse=None,
    )
    assert m.identifiant == "abc"
    assert m.harnais == "Codex"
    assert m.question == "relire transport.py"
    assert m.sujet == "relire transport.py"
    assert m.depose_a == 1.0
    assert m.etat == "en_cours"
    assert m.reponse is None


def test_registre_deposer_en_cours_prets_annonce_oublier():
    r = RegistreMandats()
    m = Mandat(
        identifiant="m1",
        harnais="Codex",
        question="q",
        sujet="s",
        depose_a=time.monotonic(),
        etat="en_cours",
    )
    r.deposer(m)
    assert r.en_cours() == [m]
    assert r.prets() == []
    m.etat = "fini"
    assert r.en_cours() == []
    assert r.prets() == [m]
    r.marquer_annonce("m1")
    assert r.prets() == []
    r.oublier("m1")
    assert r.en_cours() == []
    assert r.prets() == []


def test_registre_refuse_au_dela_de_trois_en_cours():
    r = RegistreMandats()
    assert MAX_MANDATS_EN_COURS == 3
    for i in range(3):
        r.deposer(
            Mandat(
                identifiant=f"m{i}",
                harnais="Codex",
                question="q",
                sujet="s",
                depose_a=time.monotonic(),
                etat="en_cours",
            )
        )
    with pytest.raises(PleinMandats) as pi:
        r.deposer(
            Mandat(
                identifiant="m3",
                harnais="Claude",
                question="q",
                sujet="s",
                depose_a=time.monotonic(),
                etat="en_cours",
            )
        )
    assert "patiente" not in str(pi.value).lower()
    assert pi.value.phrase
    assert r.en_cours() == r.en_cours()
    assert len(r.en_cours()) == 3


def test_un_mandat_fini_ne_compte_pas_dans_la_borne():
    r = RegistreMandats()
    for i in range(3):
        m = Mandat(
            identifiant=f"m{i}",
            harnais="Codex",
            question="q",
            sujet="s",
            depose_a=time.monotonic(),
            etat="en_cours" if i < 2 else "fini",
        )
        r.deposer(m)
    r.deposer(
        Mandat(
            identifiant="ok",
            harnais="Claude",
            question="q",
            sujet="s",
            depose_a=time.monotonic(),
            etat="en_cours",
        )
    )
    assert len(r.en_cours()) == 3


# --- extraction + phrases -----------------------------------------------------


def test_extraire_harnais_et_sujet():
    assert extraire_harnais("demande a Codex de relire transport.py") == "Codex"
    assert extraire_sujet("demande a Codex de relire transport.py") == "relire transport.py"
    assert extraire_harnais("demande à Claude de relire le code") == "Claude"
    assert extraire_sujet("demande à Claude de relire le code") == "relire le code"


def test_accuse_est_un_gabarit_sans_attente(lang_env=None):
    phrase = phrase_accuse("Codex", "relire transport.py")
    assert "Codex" in phrase
    assert "relire transport.py" in phrase
    assert "préviens" in phrase.lower() or "previens" in phrase.lower()
    assert "patiente" not in phrase.lower()
    assert "instant" not in phrase.lower()
    assert "vingtaine" not in phrase.lower()


def test_arrivee_lit_le_resume_pas_le_detail():
    m = Mandat(
        identifiant="m",
        harnais="Codex",
        question="q",
        sujet="s",
        depose_a=0.0,
        etat="fini",
        reponse=_reponse(),
    )
    phrase = phrase_arrivee(m)
    assert phrase.startswith("Codex a fini")
    assert "Le fichier est propre." in phrase
    assert "Tu veux le détail" in phrase or "Tu veux le detail" in phrase
    assert "X" * 20 not in phrase
    assert "Detail long" not in phrase
    assert phrase.count("?") == 1


def test_arrivee_sans_resume_offre_quand_meme():
    m = Mandat(
        identifiant="m",
        harnais="Codex",
        question="q",
        sujet="s",
        depose_a=0.0,
        etat="fini",
        reponse=_reponse(resume_voix=""),
    )
    phrase = phrase_arrivee(m)
    assert "résumé" in phrase.lower() or "resume" in phrase.lower()
    assert "ouvre" in phrase.lower()
    assert "X" * 20 not in phrase


def test_i18n_trois_temps_fr_et_en(monkeypatch):
    monkeypatch.delenv("HA_LANG", raising=False)
    monkeypatch.delenv("HYPER_AMBIENT_LANG", raising=False)
    assert "{harnais}" in t("mandat.accuse") or "Codex" in phrase_accuse("Codex", "ça")
    accuse = t("mandat.accuse", harnais="Codex", sujet="relire transport.py")
    assert "Codex" in accuse
    assert "patiente" not in accuse.lower()
    assert t("mandat.rappel", harnais="Codex")
    assert t("mandat.fini", harnais="Codex")
    assert t("mandat.offre")
    monkeypatch.setenv("HA_LANG", "en")
    accuse_en = t("mandat.accuse", harnais="Codex", sujet="review transport.py")
    assert "Codex" in accuse_en
    assert "patiente" not in accuse_en.lower()
    assert "wait" not in accuse_en.lower()
    assert t("mandat.offre")
    assert t("mandat.rappel", harnais="Codex")


def test_phrases_rappel_et_plein_prononcables():
    assert "Codex" in phrase_rappel("Codex")
    assert "patiente" not in phrase_rappel("Codex").lower()
    plein = phrase_plein()
    assert plein.strip()
    assert "patiente" not in plein.lower()


# --- confier ------------------------------------------------------------------


@runs_async
async def test_confier_rend_la_main_avant_l_appel(monkeypatch):
    import src.brain.mandat as mod

    vues = []

    async def appel(question: str) -> str:
        await asyncio.sleep(0.3)
        vues.append(question)
        return "ok"

    monkeypatch.setattr(mod, "envelopper", lambda q: f"ENV:{q}")
    monkeypatch.setattr(mod, "analyser", lambda t: _reponse(resume_voix="bref"))

    r = RegistreMandats()
    t0 = time.monotonic()
    m = await confier(r, "Codex", "relire transport.py", "relire transport.py", appel)
    assert time.monotonic() - t0 < 0.15
    assert m.etat == "en_cours"
    assert r.en_cours() == [m]
    await asyncio.sleep(0.4)
    assert m.etat == "fini"
    assert vues == ["ENV:relire transport.py"]
    assert m.reponse.resume_voix == "bref"


@runs_async
async def test_confier_avale_les_exceptions(monkeypatch):
    import src.brain.mandat as mod

    async def boom(question: str) -> str:
        raise RuntimeError("trace interne")

    monkeypatch.setattr(mod, "envelopper", lambda q: q)
    monkeypatch.setattr(mod, "analyser", lambda t: _reponse())

    r = RegistreMandats()
    m = await confier(r, "Claude", "q", "s", boom)
    await asyncio.sleep(0.05)
    assert m.etat == "echoue"
    assert m.reponse is None
    assert r.prets() == [m]


@runs_async
async def test_confier_expire_sans_rester_en_cours(monkeypatch):
    import src.brain.mandat as mod

    async def jamais(question: str) -> str:
        await asyncio.sleep(10)
        return "trop tard"

    monkeypatch.setattr(mod, "DELAI_EXPIRATION_S", 0.05)
    monkeypatch.setattr(mod, "envelopper", lambda q: q)
    monkeypatch.setattr(mod, "analyser", lambda t: _reponse())

    r = RegistreMandats()
    m = await confier(r, "Codex", "q", "s", jamais)
    await asyncio.sleep(0.15)
    assert m.etat == "echoue"
    assert m not in r.en_cours()
    assert m in r.prets()


@runs_async
async def test_confier_refuse_quand_plein():
    r = RegistreMandats()

    async def noop(question: str) -> str:
        await asyncio.sleep(60)
        return "x"

    for _ in range(3):
        await confier(r, "Codex", "q", "s", noop)
    with pytest.raises(PleinMandats):
        await confier(r, "Claude", "q", "s", noop)
    for m in r.en_cours():
        r.oublier(m.identifiant)


def test_delai_expiration_est_cinq_minutes():
    assert DELAI_EXPIRATION_S == 300.0
    assert DELAI_RAPPEL_S == 60.0


# --- branchement host-agent ---------------------------------------------------


def _charger_serve_hostagent():
    if str(RACINE) not in sys.path:
        sys.path.insert(0, str(RACINE))
    try:
        import fastapi  # noqa: F401
        import uvicorn  # noqa: F401
    except ImportError:
        for nom in ("fastapi", "fastapi.responses", "fastapi.websockets", "uvicorn"):
            sys.modules.setdefault(nom, MagicMock(name=nom))
    chemin = RACINE / "dev" / "scripts" / "serve_hostagent.py"
    spec = importlib.util.spec_from_file_location("serve_hostagent_mandat", chemin)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


serve_hostagent = _charger_serve_hostagent()


class _ASRTexte:
    def __init__(self, texte: str) -> None:
        self.texte = texte

    async def transcribe(self, audio):
        return {"text": self.texte, "latency_ms": 1.0}


class _MOUTHDouble:
    sample_rate = serve_hostagent.SAMPLE_RATE

    def __init__(self) -> None:
        self.hors_flux: list[str] = []
        self.flux: list[str] = []

    def _bloc(self):
        return {
            "audio": np.zeros(serve_hostagent.FRAME_SAMPLES, dtype=np.float32),
            "sample_rate": self.sample_rate,
        }

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
    name = "double"

    def __init__(self):
        self.appels: list[dict] = []

    async def query_streaming(self, prompt, **kw):
        self.appels.append({"prompt": prompt, **kw})
        yield {"delta": "le modele local a parle", "stop_reason": None, "ttft_ms": 1.0}
        yield {"delta": "", "stop_reason": "stop", "ttft_ms": None}


def _trames_de_parole(secondes: float = 1.0):
    n = int(serve_hostagent.SAMPLE_RATE * secondes)
    bruit = np.random.default_rng(20260920).uniform(-0.3, 0.3, n).astype(np.float32)
    return serve_hostagent._trames_depuis_pcm(bruit, [np.zeros(0, dtype=np.float32)])


def _rapport(socket):
    for message in socket.messages:
        if message.get("type") == "report":
            return message
    return None


def test_registre_pour_tour_retire_les_harnais_meme_si_demande(monkeypatch):
    monkeypatch.setenv("CODEX_BRIDGE_TOKEN", "jeton")
    monkeypatch.delenv("CLI_BRIDGE_TOKEN", raising=False)
    monkeypatch.delenv("MUSE_BRIDGE_URL", raising=False)
    monkeypatch.delenv("SEARXNG_URL", raising=False)
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    pipeline = serve_hostagent.HostPipeline()
    pipeline.registre = serve_hostagent.construire_registre(client=object())
    pipeline._client_outils = object()
    restreint = pipeline._registre_pour_tour("demande a Codex de relire transport.py")
    assert "ask_codex" not in restreint
    assert "calculer" in restreint


@runs_async
async def test_demande_harnais_accuse_sans_modele_local(monkeypatch):
    monkeypatch.setenv("CODEX_BRIDGE_TOKEN", "jeton")
    monkeypatch.delenv("CLI_BRIDGE_TOKEN", raising=False)
    monkeypatch.delenv("MUSE_BRIDGE_URL", raising=False)
    monkeypatch.delenv("SEARXNG_URL", raising=False)
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)

    pipeline = serve_hostagent.HostPipeline()
    pipeline.registre = serve_hostagent.construire_registre(client=object())
    pipeline.porte = serve_hostagent.construire_porte()
    pipeline.asr = _ASRTexte("demande a Codex de relire transport.py")
    pipeline.tts = _MOUTHDouble()
    pipeline.brain = _BrainDouble()
    pipeline._client_outils = object()
    socket = _SocketDouble()

    async def lent(question: str) -> str:
        await asyncio.sleep(30)
        return "trop tard"

    pipeline._appel_pour = lambda harnais: lent

    t0 = time.monotonic()
    await pipeline._enchainer(_trames_de_parole(), socket)
    assert time.monotonic() - t0 < 1.0
    assert pipeline.brain.appels == []
    rapport = _rapport(socket)
    assert rapport is not None
    assert "Codex" in rapport["reply"]
    assert "relire transport.py" in rapport["reply"]
    assert "patiente" not in rapport["reply"].lower()
    assert "le modele local a parle" not in rapport["reply"]
    assert pipeline._mandats.en_cours()
    for m in list(pipeline._mandats.en_cours()):
        pipeline._mandats.oublier(m.identifiant)
    if pipeline._tache_mandats is not None and not pipeline._tache_mandats.done():
        pipeline._tache_mandats.cancel()


@runs_async
async def test_bonjour_ne_depose_pas_de_mandat(monkeypatch):
    pipeline = serve_hostagent.HostPipeline()
    pipeline.asr = _ASRTexte("Bonjour.")
    pipeline.tts = _MOUTHDouble()
    pipeline.brain = _BrainDouble()
    socket = _SocketDouble()
    await pipeline._enchainer(_trames_de_parole(), socket)
    assert pipeline.brain.appels
    assert pipeline._mandats.en_cours() == []
    assert _rapport(socket)["reply"] == "le modele local a parle"


@runs_async
async def test_annonce_arrivee_quand_parole_libre():
    pipeline = serve_hostagent.HostPipeline()
    pipeline.tts = _MOUTHDouble()
    pipeline._websocket = _SocketDouble()
    m = Mandat(
        identifiant="m1",
        harnais="Codex",
        question="q",
        sujet="s",
        depose_a=time.monotonic(),
        etat="fini",
        reponse=_reponse(),
    )
    pipeline._mandats.deposer(m)
    leftover = [np.zeros(0, dtype=np.float32)]
    await pipeline.annoncer_mandats_prets(pipeline._websocket, leftover)
    assert m.annonce_faite or m not in pipeline._mandats.prets()
    dits = pipeline.tts.hors_flux
    assert dits
    assert "Codex a fini" in dits[0]
    assert "X" * 20 not in dits[0]
    badges = [msg for msg in pipeline._websocket.messages if msg.get("type") == "mandat_badge"]
    assert badges
    assert "SetForegroundWindow" not in str(pipeline._websocket.messages)


@runs_async
async def test_annonce_arrivee_est_un_tour_transport_autonome():
    """Une annonce apres un tour clos porte sa propre fin de tour."""
    pipeline = serve_hostagent.HostPipeline()
    pipeline.tts = _MOUTHDouble()
    socket = _SocketDouble()
    mandat = Mandat(
        identifiant="m-fin",
        harnais="Codex",
        question="q",
        sujet="s",
        depose_a=time.monotonic(),
        etat="fini",
        reponse=_reponse(),
    )
    pipeline._mandats.deposer(mandat)
    # Fin du tour conversationnel deja consommee par le client.
    await pipeline._envoyer(socket, [])
    await pipeline.annoncer_mandats_prets(socket, [np.zeros(0, dtype=np.float32)])

    audio = [
        index
        for index, message in enumerate(socket.messages)
        if message.get("primitive") == "audio.render" and message.get("frames")
    ]
    fins = [
        index
        for index, message in enumerate(socket.messages)
        if message.get("primitive") == "audio.render" and not message.get("frames")
    ]
    assert audio
    assert any(fin > audio[-1] for fin in fins)


@runs_async
async def test_annonce_arrivee_attend_si_tour_en_cours():
    pipeline = serve_hostagent.HostPipeline()
    pipeline.tts = _MOUTHDouble()
    socket = _SocketDouble()
    m = Mandat(
        identifiant="m1",
        harnais="Codex",
        question="q",
        sujet="s",
        depose_a=time.monotonic(),
        etat="fini",
        reponse=_reponse(),
    )
    pipeline._mandats.deposer(m)
    leftover = [np.zeros(0, dtype=np.float32)]
    await pipeline._lock.acquire()
    try:
        await pipeline.annoncer_mandats_prets(socket, leftover)
        assert pipeline.tts.hors_flux == []
        assert m in pipeline._mandats.prets()
    finally:
        pipeline._lock.release()


@runs_async
async def test_rappel_a_60s_seulement_si_silence(monkeypatch):
    pipeline = serve_hostagent.HostPipeline()
    pipeline.tts = _MOUTHDouble()
    socket = _SocketDouble()
    m = Mandat(
        identifiant="m1",
        harnais="Codex",
        question="q",
        sujet="s",
        depose_a=time.monotonic() - 61,
        etat="en_cours",
    )
    pipeline._mandats.deposer(m)
    pipeline._dernier_parole_a = time.monotonic() - 61
    leftover = [np.zeros(0, dtype=np.float32)]
    await pipeline.annoncer_mandats_prets(socket, leftover)
    assert any("prend" in p.lower() or "time" in p.lower() for p in pipeline.tts.hors_flux)
    n = len(pipeline.tts.hors_flux)
    await pipeline.annoncer_mandats_prets(socket, leftover)
    assert len(pipeline.tts.hors_flux) == n


def test_badge_i18n_sans_elevation():
    assert "prêt" in t("mandat.badge", n=1).lower() or "ready" in t("mandat.badge", n=1).lower()
    assert "foreground" not in t("mandat.badge", n=1).lower()
