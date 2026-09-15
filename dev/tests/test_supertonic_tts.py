"""
MOUTH : Supertonic-3, voix feminine lente (15 sept).

Thomas : « suave, feminine, agreable, qui parle plutot lentement ». Le moteur
est remplace par un double : aucun ONNX n'est charge ici. On verifie ce que le
host-agent consomme — `audio` int16 et `sample_rate` — et ce que la voix
promet : francais, vitesse reglee, une synthese par phrase.
"""
import asyncio

import numpy as np

from src.mouth.supertonic_tts import SupertonicTTS


class FauxMoteur:
    sample_rate = 44100

    def __init__(self):
        self.appels = []

    def get_voice_style(self, nom):
        return f"style:{nom}"

    def synthesize(self, text, voice_style, speed, lang, **_):
        self.appels.append((text, voice_style, speed, lang))
        return np.full(4410, 0.5, dtype=np.float32), None


def _voix(**kw):
    tts = SupertonicTTS(style="F5", speed=0.88, profile="flat", **kw)
    tts.engine = FauxMoteur()
    tts._style = tts.engine.get_voice_style("F5")
    tts.sample_rate = tts.engine.sample_rate
    return tts


async def _tokens(parts):
    for p in parts:
        yield p


def test_synthesize_rend_int16_au_taux_du_moteur():
    tts = _voix()
    out = asyncio.run(tts.synthesize("Bonsoir Thomas."))
    assert out["audio"].dtype == np.int16 and out["audio"].size == 4410
    assert out["sample_rate"] == 44100
    assert tts.engine.appels == [("Bonsoir Thomas.", "style:F5", 0.88, "fr")]


def test_stream_une_synthese_par_phrase_puis_final():
    tts = _voix()

    async def run():
        return [o async for o in tts.synthesize_stream(
            _tokens(["Bonsoir Thomas, je suis là. ", "Dis-moi si mon rythme te convient."]))]

    outs = asyncio.run(run())
    textes = [a[0] for a in tts.engine.appels]
    assert textes == ["Bonsoir Thomas, je suis là.", "Dis-moi si mon rythme te convient."]
    assert outs[-1]["is_final"] is True
    assert all(o["sample_rate"] == 44100 for o in outs)


def test_flush_passe_devant():
    tts = _voix()

    async def run():
        return [o async for o in tts.synthesize_stream(
            _tokens([{"text": "Un instant.", "flush": True}, "Voilà la réponse complète."]))]

    asyncio.run(run())
    assert tts.engine.appels[0][0] == "Un instant."
