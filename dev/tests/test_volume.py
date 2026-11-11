"""Volume parlé et gain relu après la carte figée."""
from __future__ import annotations

import inspect
from pathlib import Path

from src.mouth.volume import (
    GAIN_CARTE,
    GAIN_MAX,
    GAIN_MIN,
    _PHRASES,
    ecrire_gain,
    interpreter_volume,
    lire_gain,
    memoriser_gain,
    regler_volume,
    resoudre_gain,
)


def test_ordres_courts_reglent_le_volume():
    assert interpreter_volume("Parle plus fort.") == "monter"
    assert interpreter_volume("Tu peux monter le volume ?") == "monter"
    assert interpreter_volume("Moins fort.") == "baisser"
    assert interpreter_volume("C'est trop fort.") == "baisser"
    assert interpreter_volume("Volume normal.") == "normal"
    assert interpreter_volume("C'est quoi le volume ?") == "annoncer"
    assert interpreter_volume("A bit louder, please.") == "monter"
    assert interpreter_volume("Habla más fuerte.") == "monter"


def test_une_vraie_demande_ne_change_pas_le_volume():
    for phrase in (
        "Demande à Codex de parler plus fort dans la salle.",
        "Explique pourquoi il faut parler plus fort pendant la réunion de cet après-midi",
        "Quelle heure est-il ?",
        "",
    ):
        assert interpreter_volume(phrase) is None, phrase


def test_le_pas_est_borne():
    gain, phrase = regler_volume(GAIN_CARTE, "monter", langue="fr")
    assert gain == 12
    assert "12" in phrase
    gain, phrase = regler_volume(GAIN_MAX, "monter", langue="fr")
    assert gain == GAIN_MAX
    assert "maximum" in phrase
    gain, _phrase = regler_volume(GAIN_MIN, "baisser", langue="en")
    assert gain == GAIN_MIN
    gain, phrase = regler_volume(15, "normal", langue="fr", carte=GAIN_CARTE)
    assert gain == GAIN_CARTE
    assert "9" in phrase
    gain, phrase = regler_volume(4, "annoncer", langue="es")
    assert gain == 4
    assert "4" in phrase


def test_les_trois_langues_ont_les_memes_cles():
    assert set(_PHRASES) == {"fr", "en", "es"}
    reference = set(_PHRASES["fr"])
    for langue, table in _PHRASES.items():
        assert set(table) == reference
        assert len(set(table.values())) == len(table)
    assert _PHRASES["fr"]["monter"] != _PHRASES["en"]["monter"]


def test_le_fichier_parle_gagne_puis_sefface_au_normal(tmp_path: Path):
    chemin = tmp_path / "mouth_gain_db"
    memoriser_gain(chemin, 12, GAIN_CARTE)
    assert lire_gain(chemin) == 12
    assert resoudre_gain(GAIN_CARTE, lire_gain(chemin)) == 12
    memoriser_gain(chemin, GAIN_CARTE, GAIN_CARTE)
    assert not chemin.exists()
    assert resoudre_gain(GAIN_CARTE, lire_gain(chemin)) == GAIN_CARTE
    ecrire_gain(chemin, 99)
    assert lire_gain(chemin) == GAIN_MAX
    (tmp_path / "illisible").write_text("non", encoding="utf-8")
    assert lire_gain(tmp_path / "illisible") is None


def test_le_tour_vocal_regle_le_volume_avant_le_cerveau():
    from dev.tests.test_hostagent_env_local import serve_hostagent

    source = inspect.getsource(serve_hostagent.HostPipeline._enchainer)
    assert "interpreter_volume(prompt)" in source
    assert source.index("interpreter_volume(prompt)") < source.index("self._memoire.doit_fermer(")
    charge = inspect.getsource(serve_hostagent.HostPipeline.load)
    assert charge.index("_appliquer_env_boot()") < charge.index("gain_de_sortie(")


def test_windows_relit_les_9_db_de_la_carte_et_mac_garde_zero(tmp_path, monkeypatch):
    from dev.tests.test_hostagent_env_local import serve_hostagent

    monkeypatch.delenv("MOTHER_PROFILE", raising=False)
    windows: dict[str, str] = {}
    serve_hostagent._appliquer_env_boot(windows)
    with serve_hostagent._poser_environ(windows):
        assert serve_hostagent.gain_de_sortie() == 9.0
        chemin = tmp_path / "mouth_gain_db"
        ecrire_gain(chemin, 12)
        assert serve_hostagent.gain_de_sortie(chemin) == 12

    mac = {"MOTHER_PROFILE": "mac-16g-voix-max"}
    serve_hostagent._appliquer_env_boot(mac)
    with serve_hostagent._poser_environ(mac):
        assert os_gain(serve_hostagent) == 0.0
        assert serve_hostagent.gain_de_sortie() == 0.0


def os_gain(module) -> float:
    return module._nombre_configuration("MOUTH_OUTPUT_GAIN_DB", -1.0)


def test_la_relance_exporte_le_gain_persiste():
    texte = (Path(__file__).resolve().parents[2] / "dev/scripts/relance_hostagent.sh").read_text(encoding="utf-8")
    assert "mouth_gain_db" in texte
    assert "MOUTH_OUTPUT_GAIN_DB_FORCE" in texte
    assert "lire_carte MOUTH_OUTPUT_GAIN_DB" in texte
    assert texte.index("mouth_gain_db") < texte.index("export MOUTH_OUTPUT_GAIN_DB")
