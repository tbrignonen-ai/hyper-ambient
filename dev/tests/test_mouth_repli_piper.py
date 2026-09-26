"""Installation neuve : la voix de la carte manque, le host-agent parle quand même.

Magpie (carte figée) exige un environnement NeMo qu'aucun script du dépôt ne
pose. Avant, ``load()`` s'arrêtait (SystemExit) et Presence restait muette ;
désormais il retombe sur Piper (fetch_models.sh core) et le dit.
"""
import asyncio
from types import SimpleNamespace

import pytest

from dev.scripts import serve_hostagent
import src.ears.jev_local as jev_local
import src.mouth.magpie_tts as magpie_tts
import src.mouth.piper_tts as piper_tts


class _Voix:
    charge = True
    instances: list = []

    def __init__(self, *a, **kw):
        self.kw = kw
        type(self).instances.append(self)

    async def load_model(self):
        return type(self).charge


class _Magpie(_Voix):
    charge = False
    instances: list = []


class _Piper(_Voix):
    instances: list = []


def _pipeline(monkeypatch, backend):
    monkeypatch.setenv("MOUTH_BACKEND", backend)
    monkeypatch.setattr(serve_hostagent, "_appliquer_env_boot", lambda *a, **k: ([], []))

    async def charger_ears():
        return True

    asr = SimpleNamespace(model_size="large-v3", device="cpu", hotwords=None, load_model=charger_ears)
    monkeypatch.setattr(serve_hostagent, "construire_ears", lambda *a, **k: ("faster-whisper", asr))

    async def sante():
        return {"detail": "ok"}

    async def monter_cerveau(**_):
        return {
            "brain": SimpleNamespace(name="test", api_endpoint="-", health=sante),
            "client": None,
            "registre": SimpleNamespace(schemas=lambda: []),
            "porte": SimpleNamespace(mode="test"),
            "mandats": None,
        }

    monkeypatch.setattr(serve_hostagent, "monter_cerveau", monter_cerveau)
    monkeypatch.setattr(serve_hostagent, "nouveau_fichier_conversation", lambda: "convo.md")
    monkeypatch.setattr(jev_local, "construire_jev", lambda: object())
    _Magpie.instances, _Piper.instances = [], []
    _Piper.charge = True
    monkeypatch.setattr(magpie_tts, "MagpieTTS", _Magpie)
    monkeypatch.setattr(piper_tts, "PiperTTS", _Piper)
    pipeline = serve_hostagent.HostPipeline()
    monkeypatch.setattr(pipeline, "_assurer_veille_mandats", lambda: None)
    monkeypatch.setattr(pipeline, "_demarrer_surveillance_langue", lambda: None)
    return pipeline


def test_magpie_absent_repli_sur_piper(monkeypatch, capsys):
    pipeline = _pipeline(monkeypatch, "magpie")
    asyncio.run(pipeline.load())
    assert len(_Magpie.instances) == 1
    assert isinstance(pipeline.tts, _Piper)
    assert "repli sur piper" in capsys.readouterr().out


def test_piper_absent_aussi_arrete_le_boot(monkeypatch):
    pipeline = _pipeline(monkeypatch, "magpie")
    _Piper.charge = False
    with pytest.raises(SystemExit):
        asyncio.run(pipeline.load())


def test_piper_demande_et_absent_ne_boucle_pas(monkeypatch):
    pipeline = _pipeline(monkeypatch, "piper")
    _Piper.charge = False
    with pytest.raises(SystemExit):
        asyncio.run(pipeline.load())
    assert len(_Piper.instances) == 1
