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
    deposer_depuis_outil,
    extraire_harnais,
    extraire_sujet,
    nom_harnais_dit,
    phrase_accuse,
    phrase_depot,
    phrase_harnais_absent,
    phrase_si_harnais_non_branche,
    respecter_harnais_nomme,
    phrase_question_manquante,
    phrase_arrivee,
    phrase_plein,
    phrase_rappel,
    question_est_substantielle,
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


def test_extraire_harnais_cursor_est_un_harnais():
    """Cursor est un harnais à part, pas un alias silencieux de Codex."""
    assert extraire_harnais("demande a Cursor d'ouvrir le fichier") == "Cursor"
    assert nom_harnais_dit("demande a Cursor d'ouvrir le fichier") == "Cursor"


def test_nom_harnais_dit_garde_claude_code():
    prompt = "Demande a Claude Code de me dire quelle version de Python tourne."
    assert extraire_harnais(prompt) == "Claude"
    assert nom_harnais_dit(prompt) == "Claude Code"


def test_phrase_harnais_absent_nomme_le_demande_et_le_propose():
    phrase = phrase_harnais_absent("Cursor", propose="Codex")
    assert "Cursor" in phrase
    assert "Codex" in phrase
    assert "n'est pas connecté" in phrase
    assert phrase != phrase_harnais_absent("Cursor")


class _Registre:
    def __init__(self, noms):
        self._noms = set(noms)

    def get(self, nom):
        return nom if nom in self._noms else None


def test_respecter_harnais_nomme_recrit_codex_vers_claude():
    from src.brain.tools import ToolCall

    appel = ToolCall(id="c1", name="ask_codex", arguments={"question": "version Python"})
    appels, refus = respecter_harnais_nomme(
        "Demande a Claude Code de me dire la version.",
        [appel],
        _Registre({"ask_claude", "ask_codex"}),
    )
    assert refus is None
    assert [a.name for a in appels] == ["ask_claude"]
    assert appels[0].arguments["question"] == "version Python"


def test_respecter_harnais_nomme_refuse_si_absent_du_registre():
    from src.brain.tools import ToolCall

    appel = ToolCall(id="c1", name="ask_codex", arguments={"question": "version Python"})
    appels, refus = respecter_harnais_nomme(
        "Demande a Claude Code de me dire la version.",
        [appel],
        _Registre({"ask_codex"}),
    )
    assert appels == []
    assert "Claude Code" in refus
    assert "Codex" in refus
    assert "n'est pas connecté" in refus


def test_harnais_nomme_et_branche_ne_produit_pas_la_phrase():
    """Codex est dans le registre : on ne refuse pas, on laisse le mandat se déposer."""
    phrase = phrase_si_harnais_non_branche(
        "Demande a Codex de relire transport.py",
        _Registre({"ask_codex"}),
    )
    assert phrase is None


def test_harnais_nomme_et_non_branche_produit_la_phrase_sans_mandat():
    """Cursor est reconnu, pas branché : une phrase, pas un mandat, pas Codex saisi."""
    registre = _Registre({"ask_codex"})
    prompt = "Demande a Cursor de me resumer src/brain/router.py."
    phrase = phrase_si_harnais_non_branche(prompt, registre)
    assert phrase is not None
    assert "Cursor" in phrase
    assert "Codex" in phrase
    appels, refus = respecter_harnais_nomme(prompt, [], registre)
    assert appels == []
    assert refus == phrase


def test_muse_et_claude_non_branches_empruntent_le_meme_chemin():
    """Un seul traitement : harnais nommé, outil absent du registre."""
    registre = _Registre({"ask_codex"})
    pour_muse = phrase_si_harnais_non_branche(
        "Demande a Muse un plan pour la soutenance.", registre
    )
    pour_claude = phrase_si_harnais_non_branche(
        "Demande a Claude de relire transport.py.", registre
    )
    pour_cursor = phrase_si_harnais_non_branche(
        "Demande a Cursor d'ouvrir le fichier.", registre
    )
    assert pour_muse is not None and "Muse" in pour_muse and "Codex" in pour_muse
    assert pour_claude is not None and "Claude" in pour_claude and "Codex" in pour_claude
    assert pour_cursor is not None and "Cursor" in pour_cursor and "Codex" in pour_cursor
    assert pour_muse.count("Je peux demander") == 1
    assert pour_claude.count("Je peux demander") == 1
    assert pour_cursor.count("Je peux demander") == 1


def test_tour_sans_harnais_nomme_ne_change_pas():
    assert phrase_si_harnais_non_branche("Bonjour.", _Registre({"ask_codex"})) is None
    assert phrase_si_harnais_non_branche(
        "Quelle heure est-il ?", _Registre({"ask_codex", "calculer"})
    ) is None


def test_respecter_harnais_nomme_laisse_un_outil_local():
    from src.brain.tools import ToolCall

    appel = ToolCall(id="c1", name="calculer", arguments={"expression": "2+2"})
    appels, refus = respecter_harnais_nomme(
        "Demande a Claude Code de calculer 2+2.",
        [appel],
        _Registre({"ask_claude", "calculer"}),
    )
    assert refus is None
    assert [a.name for a in appels] == ["calculer"]


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
    assert "Le détail est dans Codex" in phrase or "Le detail est dans Codex" in phrase
    assert "X" * 20 not in phrase
    assert "Detail long" not in phrase
    assert "?" not in phrase


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


def _mandat_fini(harnais="Codex", **reponse_kw):
    return Mandat(
        identifiant="m",
        harnais=harnais,
        question="q",
        sujet="s",
        depose_a=0.0,
        etat="fini",
        reponse=_reponse(**reponse_kw),
    )


def test_resultat_riche_produit_l_invitation():
    """Un resultat_complet nettement plus long que le resume : elle renvoie."""
    phrase = phrase_arrivee(_mandat_fini())
    assert "Le fichier est propre." in phrase
    assert "Le détail est dans Codex" in phrase or "Le detail est dans Codex" in phrase
    assert phrase.count(".") >= 2
    assert "n'hésite" not in phrase.lower()
    assert "n'hesite" not in phrase.lower()


def test_resultat_court_ne_produit_pas_l_invitation():
    """Le complet tient dans le resume : renvoyer vers l'outil serait absurde."""
    resume = "Le dossier src/brain contient seize fichiers Python."
    phrase = phrase_arrivee(
        _mandat_fini(resume_voix=resume, resultat_complet=resume)
    )
    assert resume in phrase
    assert "détail est dans" not in phrase.lower()
    assert "detail est dans" not in phrase.lower()
    assert "Tu veux le détail" not in phrase
    assert "Tu veux le detail" not in phrase


def test_explication_libre_produit_l_invitation():
    """Pont vocal : resume ~= complet, mais le texte est deja une reduction."""
    texte = (
        "Le routeur classe d'abord chaque demande en local : les salutations "
        "ou ordres tres simples vont au canal reflexe, tandis que toute "
        "question, ambiguite ou demande d'action est envoyee au modele distant."
    )
    assert len(texte) >= 160
    phrase = phrase_arrivee(
        _mandat_fini(resume_voix=texte, resultat_complet=texte)
    )
    assert "Le détail est dans Codex" in phrase or "Le detail est dans Codex" in phrase


def test_invitation_nomme_le_harnais_qui_a_travaille():
    phrase = phrase_arrivee(_mandat_fini(harnais="Claude"))
    assert "Le détail est dans Claude" in phrase or "Le detail est dans Claude" in phrase
    assert "Codex" not in phrase


def test_invitation_absente_quand_le_reglage_est_desactive(monkeypatch):
    monkeypatch.setenv("VOIX_RENVOI_OUTIL", "0")
    phrase = phrase_arrivee(_mandat_fini())
    assert "Le fichier est propre." in phrase
    assert "détail est dans" not in phrase.lower()
    assert "detail est dans" not in phrase.lower()
    assert "Tu veux le détail" not in phrase
    assert "Tu veux le detail" not in phrase


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
    assert "Codex" in t("mandat.renvoi_outil", harnais="Codex")
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


@pytest.mark.parametrize(
    "question",
    ["", "Codex", "demande à Codex", "Je voudrais que tu demandes à Codex"],
)
def test_un_simple_destinataire_n_est_pas_un_mandat(question):
    assert question_est_substantielle(question) is False


def test_un_seul_mot_reel_est_un_mandat():
    """Séance du 23 sept : « fais juste un ping à Claude » rendait « ping »,
    refusé comme trop court ; elle répondait « Que veux-tu que je demande ? »."""
    assert question_est_substantielle("ping") is True
    assert question_est_substantielle("Demande à Claude ping") is True


def test_une_question_courte_mais_reelle_reste_substantielle():
    assert question_est_substantielle("la météo") is True
    assert question_est_substantielle("Demande à Codex de relire transport.py") is True


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
    # Le pont impose déjà une forme parlable. Empiler le contrat JSON
    # devant la question fait échoer la consigne au lieu du travail.
    assert vues == ["relire transport.py"]
    assert m.reponse.resume_voix == "bref"


@runs_async
async def test_le_pont_recoit_la_question_sans_contrat_json(monkeypatch):
    """Cause racine de l'écho : PREFIXE_CONTRAT + préfixe vocal du pont."""
    from src.brain.contrat_harnais import PREFIXE_CONTRAT
    import src.brain.mandat as mod

    vues = []

    async def appel(question: str) -> str:
        vues.append(question)
        return "src/brain contient quinze fichiers Python."

    monkeypatch.setattr(mod, "analyser", lambda t: _reponse(resume_voix=t[:220]))

    r = RegistreMandats()
    await confier(r, "Codex", "combien de fichiers Python dans src/brain", "fichiers Python", appel)
    await asyncio.sleep(0.05)
    assert vues
    assert PREFIXE_CONTRAT not in vues[0]
    assert "JSON" not in vues[0]
    assert vues[0] == "combien de fichiers Python dans src/brain"


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


def test_registre_pour_tour_garde_les_harnais_a_chaque_tour(monkeypatch):
    monkeypatch.setenv("CODEX_BRIDGE_TOKEN", "jeton")
    monkeypatch.delenv("CLI_BRIDGE_TOKEN", raising=False)
    monkeypatch.delenv("MUSE_BRIDGE_URL", raising=False)
    monkeypatch.delenv("SEARXNG_URL", raising=False)
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    pipeline = serve_hostagent.HostPipeline()
    pipeline.registre = serve_hostagent.construire_registre(
        client=object(), registre_mandats=pipeline._mandats
    )
    pipeline._client_outils = object()
    registre = pipeline._registre_pour_tour("envoie une tache a Codex")
    assert "ask_codex" in registre
    assert "calculer" in registre


@runs_async
async def test_appel_harnais_depose_un_mandat_et_rend_la_main(monkeypatch):
    monkeypatch.setenv("CODEX_BRIDGE_TOKEN", "jeton")
    monkeypatch.delenv("CLI_BRIDGE_TOKEN", raising=False)
    monkeypatch.delenv("MUSE_BRIDGE_URL", raising=False)
    monkeypatch.delenv("SEARXNG_URL", raising=False)
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)

    pipeline = serve_hostagent.HostPipeline()
    pipeline.registre = serve_hostagent.construire_registre(
        client=object(), registre_mandats=pipeline._mandats
    )
    pipeline.porte = serve_hostagent.construire_porte()
    pipeline.asr = _ASRTexte("demande a Codex de relire transport.py")
    pipeline.tts = _MOUTHDouble()
    from src.brain.tools import ToolCall

    class _BrainQuiConfie(_BrainDouble):
        async def query_streaming(self, prompt, **kw):
            self.appels.append({"prompt": prompt, **kw})
            yield {
                "delta": "",
                "stop_reason": "tool_calls",
                "tool_calls": [
                    ToolCall(
                        id="mandat-codex",
                        name="ask_codex",
                        arguments={"question": "une toute petite tache de test"},
                        raw_arguments='{"question":"une toute petite tache de test"}',
                    )
                ],
            }

    pipeline.brain = _BrainQuiConfie()
    pipeline._client_outils = object()
    socket = _SocketDouble()

    async def lent(question: str) -> str:
        await asyncio.sleep(30)
        return "trop tard"

    pipeline.registre.get("ask_codex").handler.pont = lent

    t0 = time.monotonic()
    await pipeline._enchainer(_trames_de_parole(), socket)
    assert time.monotonic() - t0 < 1.0
    assert len(pipeline.brain.appels) == 1
    rapport = _rapport(socket)
    assert rapport is not None
    assert "Codex" in rapport["reply"]
    assert "préviens" in rapport["reply"].lower() or "previens" in rapport["reply"].lower()
    assert "patiente" not in rapport["reply"].lower()
    assert "le modele local a parle" not in rapport["reply"]
    assert pipeline._mandats.en_cours()
    for m in list(pipeline._mandats.en_cours()):
        pipeline._mandats.oublier(m.identifiant)
    if pipeline._tache_mandats is not None and not pipeline._tache_mandats.done():
        pipeline._tache_mandats.cancel()


@runs_async
async def test_cursor_non_branche_ne_depose_rien_et_dit_la_phrase(monkeypatch):
    """Chemin vocal : nommer Cursor ne saisit pas Codex et ne dépose pas de mandat."""
    monkeypatch.setenv("CODEX_BRIDGE_TOKEN", "jeton")
    monkeypatch.delenv("CLI_BRIDGE_TOKEN", raising=False)
    monkeypatch.delenv("MUSE_BRIDGE_URL", raising=False)
    monkeypatch.delenv("SEARXNG_URL", raising=False)
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)

    pipeline = serve_hostagent.HostPipeline()
    pipeline.registre = serve_hostagent.construire_registre(
        client=object(), registre_mandats=pipeline._mandats
    )
    pipeline.porte = serve_hostagent.construire_porte()
    pipeline.asr = _ASRTexte(
        "Demande a Cursor de me resumer le fichier src/brain/router.py."
    )
    pipeline.tts = _MOUTHDouble()
    from src.brain.tools import ToolCall

    class _BrainQuiSaisitCodex(_BrainDouble):
        async def query_streaming(self, prompt, **kw):
            self.appels.append({"prompt": prompt, **kw})
            yield {
                "delta": "",
                "stop_reason": "tool_calls",
                "tool_calls": [
                    ToolCall(
                        id="mandat-codex",
                        name="ask_codex",
                        arguments={"question": "résume src/brain/router.py"},
                        raw_arguments='{"question":"résume src/brain/router.py"}',
                    )
                ],
            }

    pipeline.brain = _BrainQuiSaisitCodex()
    pipeline._client_outils = object()
    socket = _SocketDouble()

    async def lent(question: str) -> str:
        await asyncio.sleep(30)
        return "trop tard"

    pipeline.registre.get("ask_codex").handler.pont = lent

    await pipeline._enchainer(_trames_de_parole(), socket)
    rapport = _rapport(socket)
    assert rapport is not None
    assert "Cursor" in rapport["reply"]
    assert "Codex" in rapport["reply"]
    assert "n'est pas connecté" in rapport["reply"]
    assert pipeline._mandats.en_cours() == []
    if pipeline._tache_mandats is not None and not pipeline._tache_mandats.done():
        pipeline._tache_mandats.cancel()


@runs_async
async def test_handler_depot_ne_depend_pas_d_un_verbe_ou_d_une_regex():
    r = RegistreMandats()

    async def lent(question: str) -> str:
        await asyncio.sleep(30)
        return "trop tard"

    t0 = time.monotonic()
    phrase = await deposer_depuis_outil(r, "Claude", "une tache de test", lent)
    assert time.monotonic() - t0 < 1.0
    assert phrase == phrase_depot("Claude")
    assert len(r.en_cours()) == 1
    for mandat in r.en_cours():
        r.oublier(mandat.identifiant)


@runs_async
async def test_depot_vide_demande_la_question_sans_appel_ni_mandat():
    r = RegistreMandats()
    appels = []

    async def pont(question: str) -> str:
        appels.append(question)
        return "impossible"

    phrase = await deposer_depuis_outil(r, "Codex", "demande à Codex", pont)
    assert phrase == phrase_question_manquante("Codex")
    assert appels == []
    assert r.en_cours() == []


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
async def test_annonce_sans_audio_reste_a_annoncer():
    """Ne jamais déclarer livré un résultat que MOUTH n'a pas produit."""
    class _MOUTHMuet(_MOUTHDouble):
        async def synthesize(self, phrase):
            self.hors_flux.append(phrase)
            return {"audio": np.zeros(0, dtype=np.float32), "sample_rate": self.sample_rate}

    pipeline = serve_hostagent.HostPipeline()
    pipeline.tts = _MOUTHMuet()
    socket = _SocketDouble()
    mandat = Mandat(
        identifiant="m-muet",
        harnais="Codex",
        question="q",
        sujet="s",
        depose_a=time.monotonic(),
        etat="fini",
        reponse=_reponse(),
    )
    pipeline._mandats.deposer(mandat)

    await pipeline.annoncer_mandats_prets(socket, [np.zeros(0, dtype=np.float32)])

    assert mandat.annonce_faite is False
    assert mandat in pipeline._mandats.prets()


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


# --- séance du 23 sept : « cloud code », et « Pong. » inventé ----------------

def test_cloud_code_entendu_par_whisper_est_claude_code():
    from src.brain.mandat import redresser_harnais

    texte = redresser_harnais(
        "Est-ce que tu arrives à connecter un cloud code et à lui dire ping ?"
    )
    assert "Claude Code" in texte
    assert extraire_harnais(texte) == "Claude"
    assert redresser_harnais("le cloud est lent") == "le cloud est lent"


@pytest.mark.parametrize(
    "prompt, attendu",
    [
        ("Demande à Claude justement, tu lui dis ping et tu attends sa réponse.", "ask_claude"),
        ("Est-ce que tu arrives à connecter un Claude Code et à lui dire ping ?", "ask_claude"),
        ("Demande à Codex combien de fichiers Python il y a.", "ask_codex"),
        ("Fais juste un ping à Codex et donne moi sa réponse", "ask_codex"),
    ],
)
def test_une_demande_explicite_a_un_harnais_force_son_outil(prompt, attendu):
    from src.brain.mandat import outil_exige

    assert outil_exige(prompt, _Registre({"ask_claude", "ask_codex"})) == attendu


@pytest.mark.parametrize(
    "prompt",
    ["Qu'est-ce que Codex ?", "Tu connais Claude ?", "Quel temps fait-il ?"],
)
def test_nommer_sans_demander_ne_force_rien(prompt):
    from src.brain.mandat import outil_exige

    assert outil_exige(prompt, _Registre({"ask_claude", "ask_codex"})) is None


def test_harnais_non_branche_ne_force_rien():
    from src.brain.mandat import outil_exige

    assert outil_exige("Demande à Claude de relire.", _Registre({"ask_codex"})) is None
