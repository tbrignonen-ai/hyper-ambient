"""Transcriptions locales, un fichier Markdown par conversation."""
from datetime import datetime, timedelta, timezone
from pathlib import Path

from test_hostagent_env_local import serve_hostagent


CLES_SECRETES = (
    "API_KEY",
    "TOKEN",
    "SECRET",
    "sk-",
    "Bearer",
)


def test_un_tour_ecrit_une_ligne(tmp_path: Path):
    chemin = serve_hostagent.nouveau_fichier_conversation(
        quand=datetime(2026, 9, 21, 23, 42),
        dossier=tmp_path,
    )
    serve_hostagent.ecrire_ligne_conversation(
        chemin, "Toi", "Bonjour.", heure=datetime(2026, 9, 21, 23, 42, 1),
    )
    lignes = [
        ligne
        for ligne in chemin.read_text(encoding="utf-8").splitlines()
        if ligne.strip() and not ligne.startswith("#")
    ]
    assert len(lignes) == 1
    assert "Bonjour." in lignes[0]
    assert "Toi" in lignes[0]


def test_deux_tours_ecrivent_deux_lignes(tmp_path: Path):
    chemin = serve_hostagent.nouveau_fichier_conversation(
        quand=datetime(2026, 9, 21, 23, 42),
        dossier=tmp_path,
    )
    serve_hostagent.ecrire_ligne_conversation(
        chemin, "Toi", "Bonjour.", heure=datetime(2026, 9, 21, 23, 42, 1),
    )
    serve_hostagent.ecrire_ligne_conversation(
        chemin, "hyper-ambient", "Je vais bien.",
        heure=datetime(2026, 9, 21, 23, 42, 2),
    )
    lignes = [
        ligne
        for ligne in chemin.read_text(encoding="utf-8").splitlines()
        if ligne.strip() and not ligne.startswith("#")
    ]
    assert len(lignes) == 2
    assert "Bonjour." in lignes[0]
    assert "Je vais bien." in lignes[1]


def test_fichier_relisible_sans_secret(tmp_path: Path):
    chemin = serve_hostagent.nouveau_fichier_conversation(
        quand=datetime(2026, 9, 21, 23, 42),
        dossier=tmp_path,
    )
    serve_hostagent.ecrire_ligne_conversation(
        chemin, "Toi", "Demande à Codex de lister les .py.",
        heure=datetime(2026, 9, 21, 23, 42, 10),
    )
    serve_hostagent.ecrire_ligne_conversation(
        chemin, "→ Codex", "lister les .py",
        heure=datetime(2026, 9, 21, 23, 42, 11),
    )
    serve_hostagent.ecrire_ligne_conversation(
        chemin, "← Codex", "12 fichiers.",
        heure=datetime(2026, 9, 21, 23, 43, 5),
    )
    texte = chemin.read_text(encoding="utf-8")
    assert texte.startswith("#")
    assert "23:42:10" in texte
    assert "Toi" in texte
    assert "→ Codex" in texte
    assert "← Codex" in texte
    for secret in CLES_SECRETES:
        assert secret not in texte


def test_dossier_conteneur_passe_par_le_volume_data():
    """En conteneur, /workspace/data est monté vers ./data sur l'hôte."""
    dossier = serve_hostagent.dossier_conversations(
        environ={"HA_CONVERSATIONS_DIR": ""}
    )
    # Le test tourne sur l'hôte : LOCALAPPDATA, ou /workspace/data s'il existe.
    # L'override doit toujours gagner, c'est le chemin de preuve.
    force = serve_hostagent.dossier_conversations(
        environ={"HA_CONVERSATIONS_DIR": r"C:\Users\x\AppData\Local\hyper-ambient\conversations"}
    )
    assert force == Path(r"C:\Users\x\AppData\Local\hyper-ambient\conversations")
    assert "conversations" in str(dossier).replace("\\", "/")


def test_horodatage_suit_l_heure_de_paris(tmp_path: Path):
    """Le conteneur est en UTC ; le fondateur cherche à l'heure locale."""
    utc = datetime(2026, 9, 20, 23, 52, 53, tzinfo=timezone.utc)
    local = serve_hostagent.maintenant_local(utc)
    assert local.tzinfo is not None
    assert local.utcoffset() == timedelta(hours=2)
    assert local.hour == 1
    assert local.day == 21
    chemin = serve_hostagent.nouveau_fichier_conversation(quand=local, dossier=tmp_path)
    assert "2026-09-21_01-52" in chemin.name
    texte = chemin.read_text(encoding="utf-8")
    assert "2026-09-21 01:52" in texte
    serve_hostagent.ecrire_ligne_conversation(
        chemin, "Toi", "bonjour", heure=local,
    )
    assert "01:52:53" in chemin.read_text(encoding="utf-8")
