"""
MOUTH : MagpieTTS multilingual, voix Sofia, CUDA par défaut.

Même contrat que Supertonic : audio int16, une synthèse par phrase,
moteur chargé une fois. Les nombres passent en lettres avant l'appel.
Le binaire n'est pas relancé à chaque phrase — le double n'est jamais
recréé. MOUTH_DEVICE=cuda, repli cpu si CUDA indisponible. Les phrases
longues se coupent aux virgules pour le premier son.
"""
import asyncio
from pathlib import Path

import numpy as np

from src.mouth.magpie_tts import MagpieTTS


class FauxMoteur:
    sample_rate = 22050

    def __init__(self):
        self.appels = []

    def synthesize(self, text, voice, language, **_):
        self.appels.append((text, voice, language))
        return np.full(2205, 0.5, dtype=np.int16)


def _voix(**kw):
    tts = MagpieTTS(voice="Sofia", language="fr", device="cpu", **kw)
    tts.engine = FauxMoteur()
    tts.sample_rate = tts.engine.sample_rate
    return tts


async def _tokens(parts):
    for p in parts:
        yield p


def test_defauts_sofia_fr_cuda(monkeypatch):
    monkeypatch.delenv("MOUTH_DEVICE", raising=False)
    monkeypatch.setattr("src.mouth.magpie_tts._cuda_disponible", lambda: True)
    tts = MagpieTTS()
    assert tts.voice == "Sofia"
    assert tts.language == "fr"
    assert tts.device == "cuda"


def test_repli_cpu_si_cuda_indisponible(monkeypatch):
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "")
    tts = MagpieTTS(device="cuda")
    assert tts.device == "cpu"


def test_mouth_device_env_cuda(monkeypatch):
    monkeypatch.setattr("src.mouth.magpie_tts._cuda_disponible", lambda: True)
    monkeypatch.setenv("MOUTH_DEVICE", "cuda")
    tts = MagpieTTS()
    assert tts.device == "cuda"


def test_synthesize_rend_int16_et_verbalise_les_nombres():
    tts = _voix()
    out = asyncio.run(tts.synthesize("Rendez-vous jeudi 24 septembre à 15h30."))
    assert out["audio"].dtype == np.int16 and out["audio"].size == 2205
    assert out["sample_rate"] == 22050
    texte, voix, langue = tts.engine.appels[0]
    assert voix == "Sofia" and langue == "fr"
    assert "vingt-quatre" in texte and "quinze heures trente" in texte
    assert "24" not in texte and "15h30" not in texte


def test_deux_phrases_reutilisent_le_meme_moteur():
    tts = _voix()
    moteur = tts.engine
    asyncio.run(tts.synthesize("Bonsoir."))
    asyncio.run(tts.synthesize("Je suis là."))
    assert tts.engine is moteur
    assert [a[0] for a in moteur.appels] == ["Bonsoir.", "Je suis là."]


def test_stream_une_synthese_par_phrase_puis_final():
    tts = _voix()

    async def run():
        return [o async for o in tts.synthesize_stream(
            _tokens(["Bonsoir Thomas, je suis là. ", "Dis-moi si mon rythme te convient."]))]

    outs = asyncio.run(run())
    textes = [a[0] for a in tts.engine.appels]
    assert textes == ["Bonsoir Thomas, je suis là.", "Dis-moi si mon rythme te convient."]
    assert outs[-1]["is_final"] is True
    assert all(o["sample_rate"] == 22050 for o in outs)


def test_flush_passe_devant():
    tts = _voix()

    async def run():
        return [o async for o in tts.synthesize_stream(
            _tokens([{"text": "Un instant.", "flush": True}, "Voilà la réponse complète."]))]

    asyncio.run(run())
    assert tts.engine.appels[0][0] == "Un instant."


def test_stream_phrase_longue_coupe_a_la_virgule():
    tts = _voix()
    phrase = (
        "Rendez-vous jeudi vingt-quatre septembre à quinze heures trente, "
        "au douze rue des Lilas."
    )

    async def run():
        return [o async for o in tts.synthesize_stream(_tokens([phrase]))]

    outs = asyncio.run(run())
    textes = [a[0] for a in tts.engine.appels]
    assert len(textes) == 2
    assert "trente" in textes[0] and "Lilas" not in textes[0]
    assert "Lilas" in textes[1]
    assert outs[0]["index"] == 0 and outs[-1]["is_final"] is True


def test_hostagent_branche_magpie():
    src = Path("dev/scripts/serve_hostagent.py").read_text(encoding="utf-8")
    assert 'elif backend == "magpie"' in src
    assert "chargement magpie" in src
