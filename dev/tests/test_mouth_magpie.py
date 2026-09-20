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


def test_stream_premier_fragment_sans_ponctuation_est_court():
    """Une phrase d'ouverture sans virgule ne doit pas retarder le premier son.

    Mesure du 2026-09-20 sur le pont audio : Granite a ouvert par une phrase
    de 190 caracteres sans une seule virgule, aucun point de coupe n'est
    arrive avant le point final, et Magpie a synthetise le bloc entier avant
    d'emettre — 3422 ms de MOUTH sur un budget NFR-01 de 1200 ms.

    Piper avait deja le correctif (`_word_cut` + plancher d'ouverture
    distinct) ; Magpie ne l'avait jamais recu.
    """
    tts = _voix()
    phrase = (
        "Le facteur temps reel doit rester inferieur a 1 pour garantir que "
        "les calculs ne depassent pas le temps disponible et eviter les "
        "retards ou les depassements de limite dans un systeme dynamique."
    )

    async def run():
        return [o async for o in tts.synthesize_stream(_tokens([phrase]))]

    outs = asyncio.run(run())
    textes = [a[0] for a in tts.engine.appels]
    # Le premier fragment borne le premier son : il doit etre court.
    assert len(textes[0]) <= 34, f"premier fragment de {len(textes[0])} car. : {textes[0]!r}"

    # Rien ne doit etre perdu. Le temoin passe la meme phrase en un seul bloc
    # (flush), ce qui traverse les memes conversions — les nombres en lettres
    # notamment — sans dependre de leur detail d'implementation.
    temoin = _voix()

    async def run_temoin():
        return [o async for o in temoin.synthesize_stream(
            _tokens([{"text": phrase, "flush": True}]))]

    asyncio.run(run_temoin())
    attendu = temoin.engine.appels[0][0]
    assert " ".join(textes).split() == attendu.split()
    assert outs[0]["index"] == 0 and outs[-1]["is_final"] is True
