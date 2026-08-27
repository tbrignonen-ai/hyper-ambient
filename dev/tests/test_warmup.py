"""
Préchauffage des étages vocaux avant que le service se déclare prêt.

Mesure réelle, cinq minutes avant ces tests, sur le serveur :

    étage    à froid    à chaud
    EARS      457 ms     180 ms
    MOUTH     709 ms     174 ms
    BRAIN      27 ms      20 ms

La première phrase après lancement coûte 1226 ms contre 410 ms ensuite.
Elle dépasse le budget NFR-01 (1200 ms). Le surcoût vient surtout de
MOUTH (+535 ms) puis de EARS (+277 ms). BRAIN ne coûte presque rien :
llama-server est un processus séparé, déjà chargé.

Personne ne verra les 410 ms si la première impression dure une seconde
et quart. Le service ne doit donc se déclarer prêt qu'une fois chaud.

Le préchauffage est une optimisation, pas une condition de vie : un
étage qui lève ne doit pas empêcher le démarrage. Les doubles sont
écrits à la main — ces tests tournent sans GPU.
"""
from __future__ import annotations

import asyncio
import inspect

import numpy as np
import pytest


class _Ears:
    """Double EARS : compte les transcriptions et retient l'audio reçu."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.audios: list = []

    async def transcribe(self, audio, beam_size=5):
        self.calls.append("transcribe")
        self.audios.append(audio)
        await asyncio.sleep(0.01)
        return {"text": "", "segments": [], "latency_ms": 0.0}

    async def transcribe_stream(self, audio_chunks, partial_every_ms=500):
        self.calls.append("transcribe_stream")
        if False:
            yield {}


class _Mouth:
    """Double MOUTH : compte les synthèses ; peut lever à la demande."""

    def __init__(self, *, fail: BaseException | None = None) -> None:
        self.calls: list[str] = []
        self.fail = fail

    async def synthesize(self, text):
        self.calls.append("synthesize")
        await asyncio.sleep(0.01)
        if self.fail is not None:
            raise self.fail
        return {"audio": np.zeros(0, dtype=np.int16), "stub": True}

    async def synthesize_stream(self, text):
        self.calls.append("synthesize_stream")
        if self.fail is not None:
            raise self.fail
        if False:
            yield {}


class _Brain:
    """Double BRAIN : toute sollicitation est une erreur de conception."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def __getattr__(self, name: str):
        async def _record(*args, **kwargs):
            self.calls.append(name)
            return None

        return _record

    async def query(self, prompt):
        self.calls.append("query")
        return {"response": "", "stop_reason": "stub"}

    async def query_streaming(self, prompt):
        self.calls.append("query_streaming")
        if False:
            yield {}

    async def health(self):
        self.calls.append("health")
        return {"detail": "ok"}


async def _prechauffer(*, ears=None, mouth=None, brain=None, journal=None):
    from src.hostagent.warmup import prechauffer

    return await prechauffer(
        ears=ears if ears is not None else _Ears(),
        mouth=mouth if mouth is not None else _Mouth(),
        brain=brain if brain is not None else _Brain(),
        journal=journal if journal is not None else [],
    )


@pytest.mark.asyncio
async def test_le_prechauffage_sollicite_ears_et_mouth():
    """Les deux étages coûteux sont effectivement appelés, une fois chacun."""
    ears = _Ears()
    mouth = _Mouth()
    rapport = await _prechauffer(ears=ears, mouth=mouth, brain=_Brain())

    assert ears.calls.count("transcribe") + ears.calls.count("transcribe_stream") == 1
    assert mouth.calls.count("synthesize") + mouth.calls.count("synthesize_stream") == 1
    assert "ears" in rapport.etages_chauffes
    assert "mouth" in rapport.etages_chauffes


@pytest.mark.asyncio
async def test_le_prechauffage_n_appelle_pas_brain_inutilement():
    """BRAIN est un processus séparé déjà chaud : pas de requête par défaut.

    Le préchauffer ferait un aller-retour inutile au modèle. Si un jour
    on veut le faire, ce doit être un choix explicite, pas un effet de
    bord du démarrage.
    """
    brain = _Brain()
    await _prechauffer(ears=_Ears(), mouth=_Mouth(), brain=brain)

    assert brain.calls == []


@pytest.mark.asyncio
async def test_un_etage_qui_echoue_n_empeche_pas_le_service_de_demarrer():
    """Si MOUTH lève, prechauffer avale l'exception et journalise l'échec.

    Un préchauffage est une optimisation. En propager l'exception
    transformerait un confort (la première phrase dans le budget
    NFR-01) en panne de démarrage. Le service doit partir quand même.
    """
    journal: list = []
    mouth = _Mouth(fail=RuntimeError("mouth indisponible"))

    rapport = await _prechauffer(
        ears=_Ears(),
        mouth=mouth,
        brain=_Brain(),
        journal=journal,
    )

    assert rapport is not None
    assert journal, (
        "l'échec de MOUTH doit être journalisé : sans trace, le premier "
        "tour paiera le froid sans que personne sache pourquoi"
    )
    texte = " ".join(str(entree).lower() for entree in journal)
    assert "mouth" in texte


@pytest.mark.asyncio
async def test_le_rapport_donne_une_duree_par_etage_chauffe():
    """durees_ms porte une durée numérique positive, horloge monotone."""
    from src.hostagent import warmup

    rapport = await _prechauffer(ears=_Ears(), mouth=_Mouth(), brain=_Brain())

    assert rapport.etages_chauffes
    for etage in rapport.etages_chauffes:
        assert etage in rapport.durees_ms, f"durees_ms manque {etage}"
        valeur = rapport.durees_ms[etage]
        assert isinstance(valeur, (int, float)) and not isinstance(valeur, bool)
        assert valeur > 0

    source = inspect.getsource(warmup)
    assert "monotonic" in source, (
        "les durées d'étage se mesurent à time.monotonic, jamais à "
        "l'heure murale : un saut NTP fausserait le diagnostic de froid"
    )


@pytest.mark.asyncio
async def test_le_prechauffage_utilise_un_signal_synthetique_et_non_un_fichier():
    """Le signal d'EARS est produit en mémoire (numpy), pas lu sur disque.

    Un chemin vers data/in/question.wav ferait échouer le démarrage sur
    une machine tierce où ce fichier n'existe pas. Le préchauffage ne
    doit dépendre d'aucun WAV.
    """
    from src.hostagent import warmup

    ears = _Ears()
    await _prechauffer(ears=ears, mouth=_Mouth(), brain=_Brain())

    assert ears.audios, "EARS doit recevoir un signal pour se chauffer"
    audio = ears.audios[0]
    assert isinstance(audio, np.ndarray), (
        "le signal passé à EARS doit être un tableau numpy, pas un chemin"
    )
    assert audio.size > 0

    source = inspect.getsource(warmup)
    assert "question.wav" not in source
    assert "data/in" not in source
    assert "soundfile" not in source
    assert "wavfile" not in source
    # On vise la lecture de fichier, pas le nom de la bibliothèque : le module
    # cite librosa en prose parce que son premier resample est la dépense à
    # froid diagnostiquée. C'est `librosa.load` qui ouvrirait un fichier.
    assert "librosa.load" not in source
    assert "numpy" in source or "np." in source


from src.hostagent.warmup import prechauffer  # noqa: E402

# --- Rééchantillonnage : la vraie dépense à froid -------------------------
#
# Mesure isolée dans le conteneur : `import librosa` coûte 1 ms, mais le
# PREMIER `librosa.resample` coûte 596 ms et le second 0 ms. Le filtre est
# construit à la première conversion. Chauffer MOUTH sans chauffer ce chemin
# laisse donc l'intégralité du surcoût dans la première phrase — c'est ce qui
# a été observé : 703 ms de « MOUTH » alors que la synthèse elle-même en
# coûte 45.


@pytest.mark.asyncio
async def test_le_prechauffage_sollicite_le_rechantillonnage_quand_il_est_fourni():
    appels = []

    def rechantillonner(pcm, orig_sr):
        appels.append((len(pcm), orig_sr))
        return pcm

    rapport = await prechauffer(
        ears=_Ears(),
        mouth=_Mouth(),
        rechantillonner=rechantillonner,
    )

    assert len(appels) == 1, "le filtre ne se construit qu'au premier appel"
    assert appels[0][0] > 0, "un signal vide ne construirait aucun filtre"
    assert appels[0][1] != 16000, (
        "rééchantillonner vers son propre taux est un court-circuit : "
        "le filtre ne serait pas construit"
    )
    assert "resample" in rapport.etages_chauffes
    assert rapport.durees_ms["resample"] >= 0.0


@pytest.mark.asyncio
async def test_un_rechantillonnage_qui_echoue_n_empeche_pas_le_demarrage():
    def rechantillonner(pcm, orig_sr):
        raise RuntimeError("librosa absent")

    rapport = await prechauffer(
        ears=_Ears(),
        mouth=_Mouth(),
        rechantillonner=rechantillonner,
    )

    assert "resample" not in rapport.etages_chauffes
    assert "ears" in rapport.etages_chauffes


@pytest.mark.asyncio
async def test_le_rechantillonnage_est_optionnel():
    rapport = await prechauffer(ears=_Ears(), mouth=_Mouth())
    assert "resample" not in rapport.etages_chauffes
