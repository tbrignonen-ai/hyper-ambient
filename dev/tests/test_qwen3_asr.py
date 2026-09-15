"""
EARS: Qwen3-ASR-0.6B, même contrat que FasterWhisperASR, sans réseau.

Option 2 du CHOIX du 13 sept : STT Q4 streaming, peak annoncé 1,2 Go.
Les tests ne téléchargent rien et n'ouvrent pas de socket : le backend
est une doublure, ou le stub du modèle non chargé. vLLM est hors budget
VRAM (il réserverait une fraction du GPU) : le chargement réel passe
par transformers, le « streaming » est le re-décode par fenêtre croissante
déjà en place chez FasterWhisperASR.
"""
from __future__ import annotations

import asyncio
import functools
from types import SimpleNamespace

import numpy as np
import pytest
import torch

SAMPLE_RATE = 16000


def runs_async(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        return asyncio.run(fn(*args, **kwargs))

    return wrapper


@pytest.fixture(autouse=True)
def _hors_ligne(monkeypatch):
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")


def _asr(**kwargs):
    from src.ears.qwen3_asr import Qwen3ASR

    return Qwen3ASR(**kwargs)


class _FakeBackend:
    """Double qwen-asr : transcribe((pcm, sr), language=...) -> liste de résultats."""

    def __init__(self, texts):
        self.texts = list(texts)
        self.calls = []

    def transcribe(self, audio, language=None, **kwargs):
        self.calls.append({"audio": audio, "language": language, "kwargs": kwargs})
        text = self.texts[min(len(self.calls) - 1, len(self.texts) - 1)]
        return [SimpleNamespace(text=text, language="French")]


def test_les_defauts_sont_ceux_de_l_option_2():
    """0.6B, français, CUDA, Q4 — le peak Muse/Claude, pas le 1.7B."""
    from src.ears.qwen3_asr import PEAK_VRAM_GB, Qwen3ASR, SAMPLE_RATE as ears_sr

    asr = Qwen3ASR()
    assert asr.model_size == "0.6B"
    assert asr.model_id == "Qwen/Qwen3-ASR-0.6B"
    assert asr.language == "fr"
    assert asr.device == "cuda"
    assert asr.compute_type == "q4"
    assert asr.model is None
    assert ears_sr == 16000
    assert PEAK_VRAM_GB == pytest.approx(1.2)
    assert PEAK_VRAM_GB <= 1.2


def test_q4_ne_reserve_pas_de_vram_vllm():
    """vLLM pose gpu_memory_utilization : interdit sous le plafond 10 Go coloc."""
    import torch

    asr = _asr()
    kwargs = asr._from_pretrained_kwargs()
    assert kwargs.get("load_in_4bit") is True
    # Le frontend Conv2d n'est pas quantifie par bitsandbytes. Son entrée doit
    # suivre ses poids Half, sinon le premier tour de voix lève RuntimeError.
    assert kwargs.get("dtype") is torch.float16
    assert "gpu_memory_utilization" not in kwargs
    assert kwargs.get("max_inference_batch_size") == 1


def test_hors_cuda_ne_force_ni_q4_ni_half():
    """Le garde-fou CUDA ne doit pas rendre le backend CPU inutilisable."""
    kwargs = _asr(device="cpu")._from_pretrained_kwargs()
    assert kwargs["device_map"] == "cpu"
    assert "load_in_4bit" not in kwargs
    assert "dtype" not in kwargs


@runs_async
async def test_transcribe_sans_modele_rend_le_stub():
    asr = _asr()
    audio = np.zeros(SAMPLE_RATE, dtype=np.float32)
    result = await asr.transcribe(audio)
    assert result["text"] == "[stub]"
    assert result["segments"] == []
    assert result["rtf"] == 0.0
    assert result["latency_ms"] == 0.0


@runs_async
async def test_transcribe_avec_double_rend_le_texte_et_le_rtf():
    asr = _asr()
    asr.model = _FakeBackend(["bonjour"])
    audio = np.zeros(2 * SAMPLE_RATE, dtype=np.float32)
    result = await asr.transcribe(audio)
    assert result["text"] == "bonjour"
    assert result["language"] == "fr"
    assert result["audio_duration_s"] == pytest.approx(2.0)
    assert result["latency_ms"] >= 0.0
    assert result["rtf"] >= 0.0
    assert result["segments"]
    assert result["segments"][0]["text"] == "bonjour"


@runs_async
async def test_transcribe_passe_pcm_16k_et_force_le_francais():
    """Qwen attend (ndarray, sr) et le nom 'French', pas le code ISO."""
    asr = _asr()
    fake = _FakeBackend(["oui"])
    asr.model = fake
    audio = np.linspace(-0.2, 0.2, SAMPLE_RATE, dtype=np.float32)
    await asr.transcribe(audio)
    assert len(fake.calls) == 1
    passed_audio, passed_sr = fake.calls[0]["audio"]
    assert passed_sr == SAMPLE_RATE
    assert passed_audio.dtype == np.float32
    assert np.allclose(passed_audio, audio)
    assert fake.calls[0]["language"] == "French"


@runs_async
async def test_load_model_n_ouvre_pas_huggingface(monkeypatch):
    asr = _asr()

    def _interdit(*_a, **_k):
        raise AssertionError("from_pretrained réel interdit dans les tests")

    monkeypatch.setattr(asr, "_load", lambda: _FakeBackend(["ok"]))
    assert await asr.load_model() is True
    assert asr.model is not None
    result = await asr.transcribe(np.zeros(1600, dtype=np.float32))
    assert result["text"] == "ok"


@runs_async
async def test_load_model_echec_rend_false_et_garde_le_stub(monkeypatch):
    asr = _asr()

    def _boom():
        raise RuntimeError("poids absents")

    monkeypatch.setattr(asr, "_load", _boom)
    assert await asr.load_model() is False
    assert asr.model is None
    result = await asr.transcribe(np.zeros(1600, dtype=np.float32))
    assert result["text"] == "[stub]"


@runs_async
async def test_transcribe_stream_emet_des_partiels_puis_un_final():
    asr = _asr()
    asr.model = _FakeBackend(["bon", "bonjour", "bonjour."])

    async def chunks():
        # 400 ms puis encore 400 ms : le premier partiel part à 800 ms.
        yield np.zeros(int(0.4 * SAMPLE_RATE), dtype=np.float32)
        yield np.zeros(int(0.4 * SAMPLE_RATE), dtype=np.float32)

    events = [event async for event in asr.transcribe_stream(chunks(), partial_every_ms=500)]
    assert events[-1]["is_final"] is True
    assert events[-1]["text"]
    assert events[-1]["revised"] is False
    assert "rtf" in events[-1]
    assert "revisions" in events[-1]
    partiels = [e for e in events if not e["is_final"]]
    assert partiels
    assert all(e["is_final"] is False for e in partiels)


@runs_async
async def test_transcribe_stream_compte_une_revision_quand_le_prefixe_change():
    asr = _asr()
    # 1er partiel « chat », 2e « chien » (pas un préfixe) → révisé.
    asr.model = _FakeBackend(["chat", "chien", "le chien"])

    async def chunks():
        yield np.zeros(int(0.6 * SAMPLE_RATE), dtype=np.float32)
        yield np.zeros(int(0.6 * SAMPLE_RATE), dtype=np.float32)

    events = [event async for event in asr.transcribe_stream(chunks(), partial_every_ms=500)]
    partiels = [e for e in events if not e["is_final"]]
    assert any(e["revised"] is True for e in partiels)
    assert events[-1]["revisions"] >= 1
    assert asr.revisions >= 1


class _FakeAudioTower(torch.nn.Module):
    """Frontend audio : conv2d1 Half, forward pose le dtype réellement reçu."""

    def __init__(self, conv_dtype):
        super().__init__()
        self.conv2d1 = torch.nn.Conv2d(1, 2, 3, padding=1, bias=True)
        self.conv2d1.to(dtype=conv_dtype)
        self.seen = None

    def forward(self, input_features, feature_lens=None, aftercnn_lens=None):
        self.seen = {
            "dtype": input_features.dtype,
            "feature_lens": feature_lens,
            "aftercnn_lens": aftercnn_lens,
        }
        return input_features


class _FakeThinker:
    def __init__(self, tower):
        self.audio_tower = tower


class _FakeInner:
    def __init__(self, tower, model_dtype=torch.float32):
        self.thinker = _FakeThinker(tower)
        self._model_dtype = model_dtype

    @property
    def dtype(self):
        return self._model_dtype


class _FakeQwenWrapper:
    def __init__(self, tower, model_dtype=torch.float32):
        self.model = _FakeInner(tower, model_dtype)


def test_conv_half_refuse_une_entree_float32():
    """Le crash host-agent : features fp32, biais du frontend audio en Half."""
    conv = torch.nn.Conv2d(1, 2, 3, padding=1, bias=True).to(dtype=torch.float16)
    entree = torch.randn(1, 1, 8, 8, dtype=torch.float32)
    with pytest.raises(RuntimeError, match=r"bias type"):
        conv(entree)


def test_hook_caste_input_features_vers_conv2d1_half():
    """qwen-asr peut livrer du fp32 ; le corps de audio_tower doit voir du Half."""
    from src.ears.qwen3_asr import install_audio_tower_dtype_hook

    tower = _FakeAudioTower(torch.float16)
    wrapper = _FakeQwenWrapper(tower)
    handle = install_audio_tower_dtype_hook(wrapper)
    assert handle is not None
    assert wrapper._audio_tower_pre_hook is handle

    feats = torch.randn(1, 1, 8, 8, dtype=torch.float32)
    lens = torch.tensor([8], dtype=torch.int64)
    after = torch.tensor([4], dtype=torch.int32)
    tower(feats, lens, after)

    assert tower.seen["dtype"] == torch.float16
    assert tower.seen["feature_lens"] is lens
    assert tower.seen["feature_lens"].dtype == torch.int64
    assert tower.seen["aftercnn_lens"] is after
    assert tower.seen["aftercnn_lens"].dtype == torch.int32
    assert tower.conv2d1.weight.dtype == torch.float16


def test_hook_noop_si_wrapper_incomplet():
    from src.ears.qwen3_asr import install_audio_tower_dtype_hook

    vides = [
        SimpleNamespace(),
        SimpleNamespace(model=None),
        SimpleNamespace(model=SimpleNamespace()),
        SimpleNamespace(model=SimpleNamespace(thinker=SimpleNamespace())),
    ]
    for wrapper in vides:
        handle = install_audio_tower_dtype_hook(wrapper)
        assert handle is None
        assert getattr(wrapper, "_audio_tower_pre_hook", None) is None


def test_hook_noop_si_features_non_flottantes():
    from src.ears.qwen3_asr import install_audio_tower_dtype_hook

    tower = _FakeAudioTower(torch.float16)
    install_audio_tower_dtype_hook(_FakeQwenWrapper(tower))
    entiers = torch.ones(1, 1, 8, 8, dtype=torch.int64)
    tower(entiers)
    assert tower.seen["dtype"] == torch.int64


def test_load_installe_le_hook_audio_tower(monkeypatch):
    """Le chargement pose le hook ; il ne recaste pas conv2d1 vers model.dtype."""
    from src.ears.qwen3_asr import Qwen3ASR

    tower = _FakeAudioTower(torch.float16)
    wrapper = _FakeQwenWrapper(tower, model_dtype=torch.float32)

    class _Dummy:
        @staticmethod
        def from_pretrained(*_a, **_k):
            return wrapper

    monkeypatch.setitem(
        __import__("sys").modules,
        "qwen_asr",
        type("m", (), {"Qwen3ASRModel": _Dummy}),
    )
    asr = Qwen3ASR()
    loaded = asr._load()
    assert loaded is wrapper
    assert wrapper._audio_tower_pre_hook is not None
    assert tower.conv2d1.weight.dtype == torch.float16
    tower(torch.randn(1, 1, 8, 8, dtype=torch.float32))
    assert tower.seen["dtype"] == torch.float16
