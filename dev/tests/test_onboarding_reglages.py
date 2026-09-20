"""Lot B — écriture de la configuration dans `.env.local`, sans rien casser.

Le `.env.local` réel du fondateur n'est jamais lu ni écrit ici : chaque test
travaille sur un fichier temporaire, et le garde-fou `session_propre` vérifie
après coup que le fichier du dépôt n'a pas bougé. Les valeurs de clé utilisées
sont des faux, la spec interdit toute valeur réelle dans un fichier versionné.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pytest

from src.onboarding import reglages

RACINE = Path(__file__).resolve().parents[2]

FAUSSE_CLE = "sk-test-0123456789abcdefghijklmnopqrstuvwxyz"


@pytest.fixture(autouse=True)
def session_propre():
    """Réinitialise l'état de session et verrouille le `.env.local` du dépôt."""
    reglages._sauvegardes.clear()
    reel = RACINE / ".env.local"
    avant = reel.stat().st_mtime_ns if reel.exists() else None
    yield
    reglages._sauvegardes.clear()
    apres = reel.stat().st_mtime_ns if reel.exists() else None
    assert apres == avant, "le .env.local du depot a ete touche par un test"


def _env(tmp_path: Path, texte: str) -> Path:
    """Pose un `.env.local` de travail au caractère près, sans traduction."""
    chemin = tmp_path / ".env.local"
    chemin.write_bytes(texte.encode("utf-8"))
    return chemin


def _sauvegarde(chemin: Path) -> Path:
    return chemin.with_name(chemin.name + reglages.SUFFIXE_SAUVEGARDE)


# ---------------------------------------------------------------------------
# Lecture
# ---------------------------------------------------------------------------

def test_lire_ignore_commentaires_et_lignes_sans_egal(tmp_path):
    """Une valeur commentée n'est pas une valeur : c'est tout le bloc distant
    de `.env.example`, qui reste proposé mais désactivé."""
    chemin = _env(
        tmp_path,
        "# BRAIN_API_KEY=ancienne-valeur\n"
        "#   BRAIN_MODEL=commente-indente\n"
        "\n"
        "BRAIN_MODEL=step-3.7-flash\n"
        "ligne-sans-egal\n"
        "CODEX_BRIDGE_TOKEN=jeton\n",
    )
    assert reglages.lire_reglages(chemin) == {
        "BRAIN_MODEL": "step-3.7-flash",
        "CODEX_BRIDGE_TOKEN": "jeton",
    }


def test_lire_d_un_fichier_absent_rend_un_dict_vide(tmp_path):
    """Premier lancement : rien n'est posé, rien ne doit lever."""
    assert reglages.lire_reglages(tmp_path / ".env.local") == {}


def test_lire_ne_rend_pas_le_retour_chariot_windows(tmp_path):
    """Repro du boot du 19 sept : un chargeur naïf colle un `\\r` au jeton."""
    chemin = _env(tmp_path, "CLI_BRIDGE_TOKEN=jeton-claude-40\r\nBRAIN_MODEL=m\r\n")
    assert reglages.lire_reglages(chemin) == {
        "CLI_BRIDGE_TOKEN": "jeton-claude-40",
        "BRAIN_MODEL": "m",
    }


def test_lire_voit_une_derniere_ligne_sans_saut_de_ligne(tmp_path):
    chemin = _env(tmp_path, "BRAIN_MODEL=avant")
    assert reglages.lire_reglages(chemin) == {"BRAIN_MODEL": "avant"}


def test_lire_fait_gagner_la_derniere_occurrence(tmp_path):
    """python-dotenv et `docker compose --env-file` font gagner la dernière."""
    chemin = _env(tmp_path, "BRAIN_MODEL=premier\nMOUTH_BACKEND=pocket\nBRAIN_MODEL=second\n")
    assert reglages.lire_reglages(chemin)["BRAIN_MODEL"] == "second"


def test_lire_retire_des_guillemets_deja_poses(tmp_path):
    """Le fichier du fondateur peut contenir des valeurs quotées : la lecture
    rend la valeur logique, pas sa syntaxe."""
    chemin = _env(
        tmp_path,
        'BRAIN_MODEL="step-3.7-flash"\nCLI_BRIDGE_URL=\'http://hote:8766/ask\'\n',
    )
    assert reglages.lire_reglages(chemin) == {
        "BRAIN_MODEL": "step-3.7-flash",
        "CLI_BRIDGE_URL": "http://hote:8766/ask",
    }


# ---------------------------------------------------------------------------
# Écriture : rien d'autre ne bouge
# ---------------------------------------------------------------------------

def test_poser_modifie_une_cle_sur_place_sans_rien_reorganiser(tmp_path):
    """Commentaires, ordre, blocs désactivés et lignes vides doivent
    ressortir au caractère près : c'est la configuration de travail du
    fondateur, pas un fichier généré."""
    avant = (
        "# --- BRAIN : lequel repond ---\n"
        "BRAIN_SERVICE=stepfun\n"
        "\n"
        "BRAIN_API_KEY=ancienne\n"
        "# MOUTH_BACKEND=remote\n"
        "# MOUTH_REMOTE_API_KEY=\n"
        "MOUTH_BACKEND=pocket\n"
    )
    chemin = _env(tmp_path, avant)
    reglages.poser_reglage(chemin, "BRAIN_API_KEY", FAUSSE_CLE)
    assert chemin.read_bytes().decode("utf-8") == avant.replace(
        "BRAIN_API_KEY=ancienne", f"BRAIN_API_KEY={FAUSSE_CLE}"
    )


def test_poser_ajoute_une_cle_nouvelle_a_la_fin(tmp_path):
    chemin = _env(tmp_path, "BRAIN_SERVICE=stepfun\nMOUTH_BACKEND=pocket\n")
    reglages.poser_reglages(
        chemin,
        {"TYPESAFE_API_KEY": "cle-jev", "BRAIN_MODEL": "step-3.7-flash"},
    )
    assert chemin.read_bytes() == (
        b"BRAIN_SERVICE=stepfun\n"
        b"MOUTH_BACKEND=pocket\n"
        b"TYPESAFE_API_KEY=cle-jev\n"
        b"BRAIN_MODEL=step-3.7-flash\n"
    )


def test_poser_ne_reveille_pas_une_cle_commentee(tmp_path):
    """Le bloc distant commenté doit rester un choix, pas devenir actif :
    la clé est ajoutée à la fin, la ligne commentée n'est pas touchée."""
    chemin = _env(tmp_path, "# MOUTH_BACKEND=remote\nMOUTH_PROFILE=aurora\n")
    reglages.poser_reglage(chemin, "MOUTH_BACKEND", "pocket")
    assert chemin.read_bytes() == (
        b"# MOUTH_BACKEND=remote\nMOUTH_PROFILE=aurora\nMOUTH_BACKEND=pocket\n"
    )


def test_un_bloc_desactive_survit_a_l_ecriture(tmp_path):
    bloc = (
        "# Optional remote MOUTH (/audio/speech compatible).\n"
        "# MOUTH_BACKEND=remote\n"
        "# MOUTH_REMOTE_BASE_URL=https://api.stepfun.ai/step_plan/v1\n"
        "# MOUTH_REMOTE_API_KEY=\n"
    )
    chemin = _env(tmp_path, "MOUTH_BACKEND=pocket\n" + bloc)
    reglages.poser_reglages(
        chemin, {"MOUTH_BACKEND": "pocket", "BRAIN_API_KEY": FAUSSE_CLE}
    )
    assert chemin.read_bytes().decode("utf-8") == (
        "MOUTH_BACKEND=pocket\n" + bloc + f"BRAIN_API_KEY={FAUSSE_CLE}\n"
    )


def test_poser_modifie_la_derniere_occurrence_seulement(tmp_path):
    """Écrire la première laisserait deux valeurs contradictoires et celle
    qui gagne serait l'ancienne."""
    chemin = _env(
        tmp_path, "BRAIN_MODEL=premier\nMOUTH_BACKEND=pocket\nBRAIN_MODEL=second\n"
    )
    reglages.poser_reglage(chemin, "BRAIN_MODEL", "troisieme")
    assert chemin.read_bytes() == (
        b"BRAIN_MODEL=premier\nMOUTH_BACKEND=pocket\nBRAIN_MODEL=troisieme\n"
    )
    assert reglages.lire_reglages(chemin)["BRAIN_MODEL"] == "troisieme"


def test_une_derniere_ligne_sans_saut_de_ligne_est_recollee(tmp_path):
    """Sans ça la clé nouvelle se colle à la précédente et le fichier ne vaut
    plus rien pour dotenv."""
    chemin = _env(tmp_path, "BRAIN_MODEL=avant")
    reglages.poser_reglages(chemin, {"BRAIN_MODEL": "apres", "TYPESAFE_API_KEY": "cle"})
    assert chemin.read_bytes() == b"BRAIN_MODEL=apres\nTYPESAFE_API_KEY=cle\n"


def test_un_fichier_absent_est_cree_avec_son_repertoire(tmp_path):
    chemin = tmp_path / "config" / ".env.local"
    reglages.poser_reglage(chemin, "BRAIN_MODEL", "neuf")
    assert chemin.read_bytes() == b"BRAIN_MODEL=neuf\n"


def test_poser_reglages_vide_ne_touche_a_rien(tmp_path):
    """Un écran validé sans rien remplir ne crée pas un fichier vide."""
    chemin = tmp_path / ".env.local"
    reglages.poser_reglages(chemin, {})
    assert not chemin.exists()


def test_les_huit_variables_de_l_onboarding_se_posent_et_se_relisent(tmp_path):
    chemin = _env(tmp_path, "BRAIN_SERVICE=stepfun\n")
    poses = {cle: f"valeur-{cle.lower()}" for cle in reglages.CLES_ONBOARDING}
    reglages.poser_reglages(chemin, poses)
    lus = reglages.lire_reglages(chemin)
    assert {cle: lus[cle] for cle in poses} == poses
    assert chemin.read_bytes().startswith(b"BRAIN_SERVICE=stepfun\n")


# ---------------------------------------------------------------------------
# Fins de ligne et encodage
# ---------------------------------------------------------------------------

def test_les_fins_de_ligne_windows_ne_sont_pas_multipliees(tmp_path):
    chemin = _env(tmp_path, "BRAIN_MODEL=avant\r\nCODEX_BRIDGE_TOKEN=jeton\r\n")
    reglages.poser_reglages(
        chemin, {"BRAIN_MODEL": "apres", "CLI_BRIDGE_TOKEN": "autre-jeton"}
    )
    octets = chemin.read_bytes()
    assert b"\r\r" not in octets
    assert octets == (
        b"BRAIN_MODEL=apres\r\n"
        b"CODEX_BRIDGE_TOKEN=jeton\r\n"
        b"CLI_BRIDGE_TOKEN=autre-jeton\r\n"
    )


def test_un_fichier_mixte_garde_chaque_ligne_et_ajoute_en_lf(tmp_path):
    """Le `.env.local` réel est mixte (`CLI_BRIDGE_TOKEN` en CRLF) : aucune
    ligne existante ne change de fin de ligne."""
    chemin = _env(tmp_path, "A_UN=1\nB_DEUX=2\r\nC_TROIS=3\n")
    reglages.poser_reglage(chemin, "B_DEUX", "22")
    assert chemin.read_bytes() == b"A_UN=1\nB_DEUX=22\r\nC_TROIS=3\n"
    reglages.poser_reglage(chemin, "D_QUATRE", "4")
    assert chemin.read_bytes() == b"A_UN=1\nB_DEUX=22\r\nC_TROIS=3\nD_QUATRE=4\n"


def test_un_bom_est_preserve(tmp_path):
    """Notepad écrit un BOM ; le perdre ferait un diff sur la première ligne
    et casserait la lecture de la première clé."""
    chemin = tmp_path / ".env.local"
    chemin.write_bytes("\ufeffBRAIN_MODEL=avant\r\n".encode("utf-8"))
    assert reglages.lire_reglages(chemin) == {"BRAIN_MODEL": "avant"}
    reglages.poser_reglage(chemin, "BRAIN_MODEL", "apres")
    assert chemin.read_bytes() == "\ufeffBRAIN_MODEL=apres\r\n".encode("utf-8")


def test_l_utf8_est_conserve(tmp_path):
    chemin = _env(tmp_path, "")
    reglages.poser_reglage(chemin, "BRAIN_MODEL", "modèle-éloigné-été")
    assert chemin.read_bytes() == "BRAIN_MODEL=modèle-éloigné-été\n".encode("utf-8")
    assert reglages.lire_reglages(chemin)["BRAIN_MODEL"] == "modèle-éloigné-été"


# ---------------------------------------------------------------------------
# Aller-retour des valeurs
# ---------------------------------------------------------------------------

def test_une_valeur_a_espaces_se_relit_a_l_identique(tmp_path):
    chemin = _env(tmp_path, "")
    for valeur in ("step 3.7 flash", "http://hote.docker.internal:8765/ask", ""):
        reglages.poser_reglage(chemin, "BRAIN_MODEL", valeur)
        assert reglages.lire_reglages(chemin)["BRAIN_MODEL"] == valeur
    reglages.poser_reglage(chemin, "BRAIN_MODEL", "step 3.7 flash")
    assert chemin.read_bytes() == b"BRAIN_MODEL=step 3.7 flash\n"


def test_aller_retour_des_valeurs_difficiles(tmp_path):
    """Espaces de bordure, `#`, guillemets, antislashes Windows, accents,
    valeur vide, saut de ligne : rien ne doit revenir différent, et un saut
    de ligne ne doit pas injecter de ligne dans le fichier."""
    chemin = _env(tmp_path, "")
    valeurs = {
        "A_ESPACE": " debut et fin ",
        "B_DIESE": "avant#apres",
        "C_GUILLEMETS": '"entre guillemets"',
        "D_ANTISLASH": "C:\\modeles\\gguf\\mini.gguf",
        "E_ACCENT": "modèle-éloigné",
        "F_VIDE": "",
        "G_SAUT": "deux\nlignes",
        "H_ORDINAIRE": "valeur ordinaire",
    }
    reglages.poser_reglages(chemin, valeurs)
    assert reglages.lire_reglages(chemin) == valeurs
    assert chemin.read_bytes().count(b"\n") == len(valeurs)


def test_un_chemin_windows_garde_ses_antislashes(tmp_path):
    """Le cœur tourne sous Linux mais l'hôte est Windows : un modèle de voix
    peut être posé avec des antislashes."""
    chemin = _env(tmp_path, "")
    reglages.poser_reglage(chemin, "MOUTH_VOICE", "D:\\voix\\estelle.onnx")
    assert chemin.read_bytes() == b"MOUTH_VOICE=D:\\voix\\estelle.onnx\n"
    assert reglages.lire_reglages(chemin)["MOUTH_VOICE"] == "D:\\voix\\estelle.onnx"


# ---------------------------------------------------------------------------
# Atomicité et sauvegarde
# ---------------------------------------------------------------------------

def test_une_ecriture_interrompue_laisse_le_fichier_intact(tmp_path, monkeypatch):
    """Une coupure ne doit jamais laisser un `.env.local` tronqué, ni un
    temporaire plein de secrets derrière elle."""
    chemin = _env(tmp_path, "BRAIN_MODEL=avant\n")

    def _refuser(*_args, **_kwargs):
        raise OSError(28, "plus de place sur le disque")

    monkeypatch.setattr(reglages.os, "replace", _refuser)
    with pytest.raises(OSError):
        reglages.poser_reglage(chemin, "BRAIN_MODEL", "apres")

    assert chemin.read_bytes() == b"BRAIN_MODEL=avant\n"
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        chemin.name,
        chemin.name + reglages.SUFFIXE_SAUVEGARDE,
    ]


def test_la_sauvegarde_precede_la_premiere_ecriture(tmp_path):
    chemin = _env(tmp_path, "BRAIN_MODEL=avant\nMOUTH_BACKEND=pocket\n")
    reglages.poser_reglage(chemin, "BRAIN_MODEL", "apres")
    assert _sauvegarde(chemin).read_bytes() == b"BRAIN_MODEL=avant\nMOUTH_BACKEND=pocket\n"
    assert chemin.read_bytes() == b"BRAIN_MODEL=apres\nMOUTH_BACKEND=pocket\n"


def test_la_sauvegarde_ne_bouge_plus_pendant_la_session(tmp_path):
    """Le point de retour est l'état d'avant la session, pas d'avant le
    dernier écran : trois écrans validés, une seule sauvegarde."""
    chemin = _env(tmp_path, "BRAIN_MODEL=avant\n")
    reglages.poser_reglage(chemin, "BRAIN_MODEL", "milieu")
    reglages.poser_reglage(chemin, "BRAIN_MODEL", "apres")
    reglages.poser_reglages(chemin, {"TYPESAFE_API_KEY": "cle"})
    assert _sauvegarde(chemin).read_bytes() == b"BRAIN_MODEL=avant\n"
    assert chemin.read_bytes() == b"BRAIN_MODEL=apres\nTYPESAFE_API_KEY=cle\n"


def test_un_fichier_cree_par_la_session_n_est_pas_sauvegarde(tmp_path):
    """Sauvegarder un fichier qu'on vient d'écrire écraserait le point de
    retour utile — ici, il n'y en avait aucun."""
    chemin = tmp_path / ".env.local"
    reglages.poser_reglage(chemin, "BRAIN_MODEL", "neuf")
    reglages.poser_reglage(chemin, "BRAIN_MODEL", "deux")
    assert not _sauvegarde(chemin).exists()
    assert chemin.read_bytes() == b"BRAIN_MODEL=deux\n"


def test_sauvegarde_et_temporaire_restent_hors_versionnage():
    """`.gitignore` couvre `*.tmp` mais pas `.env.local.bak` : un suffixe
    `.bak` aurait rendu la sauvegarde — donc tous les secrets — versionnable.

    Le dépôt n'est pas monté en entier dans le conteneur (`src`, `dev`,
    `.env.local` seulement), donc le `.gitignore` n'est vérifié que lorsqu'il
    est visible ; le suffixe, lui, est vérifié partout.
    """
    ignore = RACINE / ".gitignore"
    if ignore.is_file():
        assert "*.tmp" in ignore.read_text(encoding="utf-8")
    assert reglages.SUFFIXE_SAUVEGARDE.endswith(".tmp")
    assert reglages.SUFFIXE_TEMPORAIRE.endswith(".tmp")


# ---------------------------------------------------------------------------
# Garde-fous
# ---------------------------------------------------------------------------

def test_reglage_present_ne_confond_pas_vide_commente_et_pose(tmp_path):
    """Une clé vide, c'est l'état d'un `.env.example` recopié : l'écran doit
    la demander, pas la croire posée."""
    chemin = _env(
        tmp_path,
        "BRAIN_API_KEY=\n"
        "   \n"
        "# CODEX_BRIDGE_TOKEN=jeton-commente\n"
        "CLI_BRIDGE_URL=http://hote.docker.internal:8766/ask\n",
    )
    assert reglages.reglage_present(chemin, "BRAIN_API_KEY") is False
    assert reglages.reglage_present(chemin, "CODEX_BRIDGE_TOKEN") is False
    assert reglages.reglage_present(chemin, "TYPESAFE_API_KEY") is False
    assert reglages.reglage_present(chemin, "CLI_BRIDGE_URL") is True

    reglages.poser_reglage(chemin, "BRAIN_API_KEY", FAUSSE_CLE)
    assert reglages.reglage_present(chemin, "BRAIN_API_KEY") is True


@pytest.mark.parametrize(
    "cle", ["", "   ", "BRAIN MODEL", "A=B", "#CACHE", "cle\ninjectee"]
)
def test_un_nom_de_variable_invalide_est_refuse_avant_toute_ecriture(tmp_path, cle):
    """Un nom tordu recopierait du texte libre dans le fichier de config ;
    rien ne doit être écrit, pas même la sauvegarde."""
    chemin = _env(tmp_path, "BRAIN_MODEL=avant\n")
    with pytest.raises(ValueError):
        reglages.poser_reglage(chemin, cle, "apres")
    assert chemin.read_bytes() == b"BRAIN_MODEL=avant\n"
    assert not _sauvegarde(chemin).exists()


def test_une_valeur_none_est_refusee_plutot_qu_ecrite(tmp_path):
    """`str(None)` poserait « None » comme clé API dans le fichier du
    fondateur, et l'écran suivant croirait le service configuré."""
    chemin = _env(tmp_path, "BRAIN_API_KEY=ancienne\n")
    with pytest.raises(TypeError):
        reglages.poser_reglages(chemin, {"BRAIN_API_KEY": None})
    assert chemin.read_bytes() == b"BRAIN_API_KEY=ancienne\n"


def test_rien_ne_part_dans_les_traces(tmp_path, caplog):
    """Règle absolue de la spec : dans les traces, la longueur d'une clé,
    jamais sa valeur — ni l'ancienne, ni la nouvelle."""
    chemin = _env(tmp_path, "BRAIN_API_KEY=ancienne-valeur\n")
    with caplog.at_level(logging.DEBUG):
        reglages.poser_reglages(chemin, {"BRAIN_API_KEY": FAUSSE_CLE})
        reglages.lire_reglages(chemin)
        reglages.reglage_present(chemin, "BRAIN_API_KEY")
    for interdit in (FAUSSE_CLE, "ancienne-valeur"):
        assert interdit not in caplog.text
