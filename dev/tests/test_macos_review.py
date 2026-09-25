"""Relecture Mac : file MLX bornée, résidence, verdict, relance Réglages."""
import asyncio
import functools
import importlib
import sys
import threading
import time
import types
from pathlib import Path

import pytest

from native.macos import controle
from native.macos.model_runtime import ModelRuntime
from src.brain.router import RouterBrain, normaliser_verdict


def run_async(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        return asyncio.run(fn(*args, **kwargs))
    return wrapper


def _lent(model, delai=0.08):
    time.sleep(delai)
    return model


@run_async
async def test_un_tour_apres_interruption_attend_au_lieu_d_etre_jete():
    """Après un STOP, la synthèse annulée finit sur Metal ; l'ASR suivante
    doit passer derrière elle, pas lever « déjà en cours » et perdre le tour."""
    runtime = ModelRuntime(residents=1)
    tts = asyncio.create_task(runtime.run("tts", lambda: "voix", _lent))
    await asyncio.sleep(0.01)
    tts.cancel()
    with pytest.raises(asyncio.CancelledError):
        await tts
    assert await runtime.run("stt", lambda: "asr") == "asr"
    await runtime.close()


@run_async
async def test_la_file_mlx_reste_bornee_a_un_tour_en_attente():
    runtime = ModelRuntime(residents=1)
    premier = asyncio.create_task(runtime.run("stt", lambda: "a", _lent))
    await asyncio.sleep(0.01)
    second = asyncio.create_task(runtime.run("stt", lambda: "a"))
    await asyncio.sleep(0.01)
    with pytest.raises(RuntimeError, match="file"):
        await runtime.run("tts", lambda: "b")
    assert await premier == "a" and await second == "a"
    await runtime.close()


@run_async
async def test_deux_residents_evitent_de_recharger_a_chaque_tour():
    runtime = ModelRuntime(residents=2)
    charges = []
    for famille in ("stt", "tts", "stt", "tts"):
        await runtime.run(famille, lambda f=famille: charges.append(f) or f)
    assert charges == ["stt", "tts"]
    await runtime.close()


@run_async
async def test_un_resident_evince_a_chaque_changement_de_famille():
    runtime = ModelRuntime(residents=1)
    charges, evictions = [], []
    for famille in ("stt", "tts", "stt"):
        await runtime.run(famille, lambda f=famille: charges.append(f) or f,
                          on_evict=lambda f=famille: evictions.append(f))
    assert charges == ["stt", "tts", "stt"]
    assert evictions == ["stt", "tts"]
    await runtime.close()


def test_residence_lue_dans_l_environnement(monkeypatch):
    monkeypatch.setenv("MOTHER_MAC_MLX_RESIDENTS", "2")
    assert ModelRuntime().residents == 2
    monkeypatch.setenv("MOTHER_MAC_MLX_RESIDENTS", "9")
    assert ModelRuntime().residents == 2
    monkeypatch.setenv("MOTHER_MAC_MLX_RESIDENTS", "n'importe")
    assert ModelRuntime().residents == 1


@pytest.mark.parametrize("brut, attendu", [
    ("REFLEXE", "REFLEXE"),
    ("REFLEXE.", "REFLEXE"),
    ("Classe: REFLEXE", "REFLEXE"),
    ("  réflexe\n", "REFLEXE"),
    ("ESCALADE", "ESCALADE"),
    ("REFLEXE un peu", "REFLEXE UN PEU"),
    ("REFLEXE ou ESCALADE", "REFLEXE OU ESCALADE"),
])
def test_verdict_mlx_tolere_la_forme_pas_le_fond(brut, attendu):
    assert normaliser_verdict(brut) == attendu


@run_async
async def test_routeur_mlx_accepte_reflexe_ponctue():
    async def classifier(prompt):
        return "Classe : Réflexe."

    router = RouterBrain(reflex=object(), deep=object(), classifier=classifier)
    assert (await router.classify("Bonjour"))["route"] == "reflex"


@run_async
async def test_fabrique_mac_vise_le_modele_charge_et_un_classifieur_court(monkeypatch):
    from src.brain import factory
    import native.macos.profile as profile

    monkeypatch.setenv("MOTHER_PROFILE", "mac-16g-voix-max")
    monkeypatch.setenv("BRAIN_LOCAL_BACKEND", "mlx")
    monkeypatch.delenv("BRAIN_DEEP", raising=False)
    monkeypatch.setattr(profile, "require_platform", lambda **_: None)
    vus = []

    class Faux:
        name = "faux"

        def __init__(self, **kw):
            self.kw = kw
            vus.append(kw)

        async def query(self, prompt, **kw):
            return {"response": "REFLEXE", "stop_reason": "stop"}

        async def initialize(self):
            self.pret = True

        async def close(self):
            self.pret = False

    monkeypatch.setattr(factory, "OpenAICompatBrain", Faux)
    router = await factory.build_router()
    assert all(kw["model"] == "default_model" for kw in vus)
    assert any(kw.get("max_tokens") == 512 for kw in vus)
    assert router.reflex.n_ctx == 2048
    classifieur = [kw for kw in vus if kw.get("max_tokens", 0) <= 8]
    assert classifieur, vus
    assert (await router.classify("Bonjour"))["route"] == "reflex"


def test_sonde_micro_attend_un_peripherique_bluetooth_lent(monkeypatch):
    from dev.tests.test_platform_audio import _charger_avec_plateforme

    macos = _charger_avec_plateforme(monkeypatch, "darwin")
    faux = types.ModuleType("sounddevice")

    class _Flux:
        def __init__(self, callback):
            self.callback = callback

        def start(self):
            threading.Timer(0.8, lambda: self.callback(b"", 0, None, None)).start()

        def stop(self):
            pass

        def close(self):
            pass

    faux.InputStream = lambda **kw: _Flux(kw["callback"])
    monkeypatch.setitem(sys.modules, "sounddevice", faux)
    assert macos.micro_accessible() is True


def test_relance_reglages_mac_passe_par_le_superviseur(tmp_path):
    def superviseur():
        until = time.monotonic() + 3
        while time.monotonic() < until:
            if controle.traiter_demande(tmp_path, lambda: True):
                return
            time.sleep(0.02)

    fil = threading.Thread(target=superviseur)
    fil.start()
    assert controle.demander_relance(tmp_path, timeout=3, pas=0.02) is True
    fil.join()
    assert not list(tmp_path.glob("relance-*"))


def test_relance_reglages_mac_echoue_proprement_sans_superviseur(tmp_path):
    assert controle.demander_relance(tmp_path, timeout=0.2, pas=0.05) is False
    assert not list(tmp_path.glob("relance-*"))


def test_relance_echouee_est_rapportee(tmp_path):
    fil = threading.Thread(target=lambda: [
        time.sleep(0.05), controle.traiter_demande(tmp_path, lambda: False)])
    fil.start()
    assert controle.demander_relance(tmp_path, timeout=2, pas=0.02) is False
    fil.join()


def test_presence_mac_delegue_la_relance_au_superviseur(monkeypatch, tmp_path):
    from native.presence import cerveau_distant as cd

    monkeypatch.setenv("MOTHER_PROFILE", "mac-16g-voix-max")
    monkeypatch.setenv("MOTHER_LOG_DIR", str(tmp_path))
    appels = []
    monkeypatch.setattr(controle, "demander_relance",
                        lambda dossier, **kw: appels.append(Path(dossier)) or True)
    monkeypatch.setattr("subprocess.run", lambda *a, **k: pytest.fail("Docker interdit sur Mac"))
    assert cd.relancer_host_agent() is True
    assert appels == [tmp_path]


def test_superviseur_reconnait_le_modele_par_chemin_resolu(tmp_path):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    supervise = importlib.import_module("dev.scripts.supervise_macos")
    modele = tmp_path / "rev"
    modele.mkdir()
    lien = tmp_path / "." / "rev"
    payload = {"data": [{"id": str(modele.resolve())}]}
    assert supervise.texte_pret(payload, lien) is True
    assert supervise.texte_pret({"data": [{"id": "autre"}]}, lien) is False
    assert supervise.texte_pret(None, lien) is False
