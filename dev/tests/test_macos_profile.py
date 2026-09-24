"""Contrats Mac sans poids, micro, réseau ni CLI."""
import asyncio
import functools
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from dev.scripts import preflight_macos
from dev.scripts.models_macos import digest_ok
from native.macos import profile
from native.macos.model_runtime import ModelRuntime
from src.ears.jev_local import JevLocal
from src.ears.jev_reflexe import JevThresholds, QUESTIONS
from src.ears.mlx_qwen3_asr import MLXQwen3ASR
from src.mouth.mlx_chatterbox_tts import MLXChatterboxTTS
from src.brain.router import RouterBrain
from native.presence import harnais_ouvert


def run_async(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        return asyncio.run(fn(*args, **kwargs))
    return wrapper


def test_profil_isole_windows_et_garde_arm64(monkeypatch):
    normal = {"CARTE_FIGEE": "1"}
    profile.apply(normal)
    assert normal["CARTE_FIGEE"] == "1"
    mac = {"MOTHER_PROFILE": profile.NAME, "CARTE_FIGEE": "1"}
    profile.apply(mac)
    assert mac["CARTE_FIGEE"] == "0"
    assert "host.docker.internal" not in json.dumps(mac)
    if sys.platform != "darwin":
        with pytest.raises(RuntimeError, match="arm64"):
            profile.require_platform()
    profile.require_platform(simulate=True)


def test_dry_run_ne_lance_rien_et_masque_les_jetons(tmp_path, monkeypatch):
    config = tmp_path / "équipe d'Emma" / "mac.env"
    config.parent.mkdir()
    config.write_text("MOTHER_PROFILE=mac-16g-voix-max\nCODEX_BRIDGE_TOKEN=secret-invisible\n", encoding="utf-8")
    monkeypatch.setattr(preflight_macos, "status", lambda family, root: {
        "status": "NOT_RUN", "missing_or_invalid": [family]})
    report = preflight_macos.inspect(config)
    assert report["status"] == "PASS"
    assert "secret-invisible" not in json.dumps(report)
    assert report["checks"]["metal_inference"]["status"] == "NOT_RUN"


def test_manifeste_verifie_sha_lfs_ou_blob_git(tmp_path):
    import hashlib

    path = tmp_path / "config.json"
    data = b'{"ok":true}'
    path.write_bytes(data)
    sha1 = hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()
    sha256 = hashlib.sha256(data).hexdigest()
    assert digest_ok(path, {"size": len(data), "sha256": None, "git_blob_sha1": sha1})
    assert digest_ok(path, {"size": len(data), "sha256": sha256, "git_blob_sha1": sha1})
    assert not digest_ok(path, {"size": len(data), "sha256": "0" * 64, "git_blob_sha1": sha1})


class FakeCollator:
    def encode_one(self, state, questions):
        if len(questions) > 3:
            raise ValueError("512 tokens")


class FakeJev:
    collator = FakeCollator()

    @staticmethod
    def _question(index, q):
        return q

    def decide(self, state, questions):
        out = []
        for q in questions:
            if q["type"] == "noul":
                out.append({"noul": 0.1})
            else:
                options = q["options"]
                probs = {option: float(index == 0) for index, option in enumerate(options)}
                if q["type"] == "choice":
                    out.append({"choice": options[0], "probabilities": probs, "confidence": 1.0})
                else:
                    out.append({"score": 0.0, "probabilities": probs, "confidence": 1.0})
        return out


@run_async
async def test_jev_local_conserve_19_distributions_typees(tmp_path):
    local = JevLocal(model_dir=tmp_path, loader=lambda _: FakeJev())
    assert await local.prechauffer()
    result = await local.evaluate("Bonjour")
    assert result is not None
    assert set(result.answers) == set(QUESTIONS)
    assert result.answers["named_harness"]["choice"] == "none"
    assert result.answers["frustration"]["score"] == 0.0
    await local.aclose()


@run_async
async def test_jev_local_refuse_reponse_incomplete(tmp_path):
    class Incomplete(FakeJev):
        def decide(self, state, questions):
            return []

    local = JevLocal(model_dir=tmp_path, loader=lambda _: Incomplete())
    assert await local.prechauffer()
    assert await local.evaluate("Bonjour") is None
    await local.aclose()


@run_async
async def test_runtime_serialize_et_evince_apres_annulation():
    runtime = ModelRuntime(residents=1)
    events = []
    began = asyncio.Event()

    def slow(model):
        import time
        time.sleep(0.08)
        events.append("slow")
        return model

    task = asyncio.create_task(runtime.run("stt", lambda: "asr", slow,
                                           on_evict=lambda: events.append("evict")))
    await asyncio.sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    # Le tour suivant attend la fin du calcul abandonné, sans chevauchement.
    assert await runtime.run("tts", lambda: "voice") == "voice"
    assert events == ["slow", "evict"]
    await runtime.close()


@run_async
async def test_asr_mlx_contrat_pcm_sans_confiance_inventee(tmp_path):
    seen = {}

    class Session:
        def transcribe(self, audio, language):
            seen["audio"] = audio
            seen["language"] = language
            return SimpleNamespace(text="bonjour", truncated=False)

    asr = MLXQwen3ASR(model_size=str(tmp_path), session_factory=lambda _: Session())
    assert await asr.load_model()
    result = await asr.transcribe(np.array([32767, -32768], dtype=np.int16))
    assert result["text"] == "bonjour"
    assert result["language_probability"] is None
    assert seen["audio"][1] == 16000
    assert seen["language"] == "French"


@run_async
async def test_chatterbox_langue_pcm_et_reference_obligatoire(tmp_path):
    ref = tmp_path / "voix.wav"
    ref.write_bytes(b"RIFF")
    seen = {}

    class Engine:
        sample_rate = 24000

        def generate(self, **kwargs):
            seen.update(kwargs)
            yield SimpleNamespace(audio=np.array([0.0, 1.0, -1.0], dtype=np.float32))

    tts = MLXChatterboxTTS(model_dir=tmp_path, reference_wav=ref,
                           loader=lambda _: Engine())
    assert await tts.load_model()
    out = await tts.synthesize("Bonjour 24")
    assert out["sample_rate"] == 24000
    assert out["audio"].dtype == np.int16
    assert seen["lang_code"] == "fr"
    assert seen["ref_audio"] == str(ref)


@run_async
async def test_routeur_mlx_valide_strictement_sans_completion():
    seen = []

    async def classifier(prompt):
        seen.append(prompt)
        return "REFLEXE"

    router = RouterBrain(reflex=object(), deep=object(), classifier=classifier)
    result = await router.classify("Bonjour")
    assert result["route"] == "reflex"
    assert len(seen) == 1 and "Classe:" in seen[0]
    router.classifier = lambda prompt: asyncio.sleep(0, result="REFLEXE un peu")
    assert (await router.classify("Bonjour"))["route"] == "escalate"


def test_harnais_mac_ouvre_un_terminal_sans_options_win32(tmp_path, monkeypatch):
    monkeypatch.setattr(harnais_ouvert.sys, "platform", "darwin")
    monkeypatch.setattr(harnais_ouvert.tempfile, "mkdtemp", lambda **_: str(tmp_path))
    calls = []

    class Proc:
        def poll(self):
            return 0

    monkeypatch.setattr(harnais_ouvert.subprocess, "Popen", lambda cmd, **kw: calls.append((cmd, kw)) or Proc())
    options = harnais_ouvert.options_console("/Users/éloïse/l'équipe", False)
    assert "startupinfo" not in options and "creationflags" not in options
    harnais_ouvert._lancer(["/opt/homebrew/bin/claude", "--resume", "s'1"], **options)
    cmd, _ = calls[0]
    assert cmd[:4] == ["open", "-a", "Terminal", "-g"]
    script = (tmp_path / "reprendre.command").read_text(encoding="utf-8")
    assert "cd '/Users/éloïse/l'\"'\"'équipe'" in script
    assert "'s'\"'\"'1'" in script


def test_sortie_macos_replie_48k_sans_modifier_la_branche_windows(monkeypatch):
    import types
    from native.hostagent import talk

    monkeypatch.setattr(talk.sys, "platform", "darwin")
    faux_soxr = types.ModuleType("soxr")
    writes = []

    class Stream:
        active = False
        channels = 1

        def start(self):
            self.active = True

        def write(self, data):
            writes.append(np.asarray(data).copy())

        def stop(self):
            self.active = False

        def close(self):
            pass

    class Soxr:
        def __init__(self, in_rate, out_rate, channels, **_):
            assert (in_rate, out_rate, channels) == (16000, 48000, 1)

        def clear(self):
            pass

        def resample_chunk(self, data, last=False):
            return np.repeat(data, 3)

    class Device:
        def query_devices(self, **_):
            return {"max_output_channels": 1, "default_samplerate": 48000, "name": "USB"}

        def query_hostapis(self):
            return []

        def OutputStream(self, **kwargs):
            if kwargs["samplerate"] == 16000:
                raise RuntimeError("16 kHz refusé")
            return Stream()

    faux_soxr.ResampleStream = Soxr
    monkeypatch.setitem(sys.modules, "soxr", faux_soxr)
    output = talk._ouvrir_sortie(Device())
    output.start()
    output.write(np.array([0.25, -0.25], dtype=np.float32))
    output.stop()
    assert len(writes[0]) == 6
    output.close()
