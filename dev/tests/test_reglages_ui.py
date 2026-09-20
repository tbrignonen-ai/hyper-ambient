"""Fenêtre Réglages de Presence — menus qui marchent, hors fil Tk.

Le `.env.local` réel du dépôt n'est jamais lu ni écrit ici. Les valeurs
utilisées sont des faux, jamais une clé réelle. Aucune sonde ne touche
le réseau : les fonctions sont injectées.
"""
from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from src.onboarding import reglages as module_reglages
from src.onboarding.sondes import Sonde

RACINE = Path(__file__).resolve().parents[2]

# Faux uniquement : suffixe volontairement banal pour pincer l'affichage.
_FAUX_SUFFIXE = "wxyz"
_FAUX_JETON = "faux-jeton-" + _FAUX_SUFFIXE
_FAUX_MODELE = "modele-test"
_FAUX_URL = "http://exemple.invalid/v1"


@pytest.fixture(autouse=True)
def session_propre():
    """Réinitialise l'état de session et verrouille le `.env.local` du dépôt."""
    module_reglages._sauvegardes.clear()
    reel = RACINE / ".env.local"
    avant = reel.stat().st_mtime_ns if reel.exists() else None
    yield
    module_reglages._sauvegardes.clear()
    apres = reel.stat().st_mtime_ns if reel.exists() else None
    assert apres == avant, "le .env.local du depot a ete touche par un test"


def _env(tmp_path: Path, texte: str) -> Path:
    chemin = tmp_path / ".env.local"
    chemin.write_bytes(texte.encode("utf-8"))
    return chemin


def _ouvrir_tk():
    try:
        import tkinter as tk
    except ModuleNotFoundError as exc:
        pytest.skip(f"Tk indisponible : {exc}")
    try:
        racine = tk.Tk()
        racine.withdraw()
        racine.destroy()
    except tk.TclError as exc:
        pytest.skip(f"Tk indisponible : {exc}")
    return tk


def _racine_tk():
    tk = _ouvrir_tk()
    try:
        racine = tk.Tk()
        racine.withdraw()
    except tk.TclError as exc:
        pytest.skip(f"Tk indisponible : {exc}")
    return tk, racine


def _textes_widgets(widget) -> list[str]:
    textes: list[str] = []
    try:
        texte = widget.cget("text")
        if texte:
            textes.append(str(texte))
    except Exception:
        pass
    try:
        textes.append(str(widget.get()))
    except Exception:
        pass
    for enfant in widget.winfo_children():
        textes.extend(_textes_widgets(enfant))
    return textes


def _pomper(racine, jusqua, timeout_s: float = 2.0) -> None:
    fin = time.time() + timeout_s
    while time.time() < fin:
        racine.update()
        if jusqua():
            return
        time.sleep(0.02)
    raise AssertionError("la fenêtre n'a pas rendu le résultat à temps")


# ---------------------------------------------------------------------------
# Logique hors Tk
# ---------------------------------------------------------------------------


def test_quatre_derniers_ne_rend_que_le_suffixe():
    from native.presence.reglages_ui import quatre_derniers

    assert quatre_derniers(_FAUX_JETON) == _FAUX_SUFFIXE
    assert quatre_derniers("") == ""
    assert quatre_derniers("   ") == ""
    assert quatre_derniers("ab") == "ab"


def test_precharger_montre_les_publics_et_masque_les_cles(tmp_path):
    from native.presence.reglages_ui import CLES_SECRETES, precharger

    chemin = _env(
        tmp_path,
        f"BRAIN_API_ENDPOINT={_FAUX_URL}\n"
        f"BRAIN_MODEL={_FAUX_MODELE}\n"
        f"BRAIN_API_KEY={_FAUX_JETON}\n"
        f"CODEX_BRIDGE_URL={_FAUX_URL}\n"
        f"CODEX_BRIDGE_TOKEN={_FAUX_JETON}\n",
    )
    champs, secrets = precharger(chemin)
    assert champs["BRAIN_API_ENDPOINT"] == _FAUX_URL
    assert champs["BRAIN_MODEL"] == _FAUX_MODELE
    assert champs["CODEX_BRIDGE_URL"] == _FAUX_URL
    for cle in CLES_SECRETES:
        assert cle not in champs
    assert "BRAIN_API_KEY" in secrets
    assert "CODEX_BRIDGE_TOKEN" in secrets
    assert _FAUX_JETON not in champs.values()


def test_valeurs_a_poser_ne_reeerit_pas_une_cle_non_retouchee():
    from native.presence.reglages_ui import valeurs_a_poser

    existants = {"BRAIN_API_KEY": _FAUX_JETON, "CODEX_BRIDGE_TOKEN": _FAUX_JETON}
    saisie = {
        "BRAIN_API_ENDPOINT": _FAUX_URL,
        "BRAIN_MODEL": _FAUX_MODELE,
        "BRAIN_API_KEY": "",
        "CODEX_BRIDGE_TOKEN": _FAUX_SUFFIXE,
        "CODEX_BRIDGE_URL": "http://exemple.invalid/ask",
    }
    posees = valeurs_a_poser(saisie, existants)
    assert "BRAIN_API_KEY" not in posees
    assert "CODEX_BRIDGE_TOKEN" not in posees
    assert posees["BRAIN_API_ENDPOINT"] == _FAUX_URL
    assert posees["BRAIN_MODEL"] == _FAUX_MODELE
    assert posees["CODEX_BRIDGE_URL"] == "http://exemple.invalid/ask"


def test_valeurs_a_poser_prend_une_cle_retouchee():
    from native.presence.reglages_ui import valeurs_a_poser

    nouveau = "faux-nouveau-abcd"
    posees = valeurs_a_poser(
        {"BRAIN_API_KEY": nouveau, "BRAIN_MODEL": "autre"},
        {"BRAIN_API_KEY": _FAUX_JETON},
    )
    assert posees["BRAIN_API_KEY"] == nouveau
    assert posees["BRAIN_MODEL"] == "autre"
    assert posees["BRAIN_API_KEY"] != _FAUX_JETON


def test_secret_effectif_reprend_l_existant_si_le_champ_est_vide():
    from native.presence.reglages_ui import secret_effectif

    assert secret_effectif("", _FAUX_JETON) == _FAUX_JETON
    assert secret_effectif(_FAUX_SUFFIXE, _FAUX_JETON) == _FAUX_JETON
    assert secret_effectif("nouveau-jeton", _FAUX_JETON) == "nouveau-jeton"


def test_lancer_hors_fil_n_execute_pas_sur_le_fil_appelant():
    from native.presence.reglages_ui import lancer_hors_fil

    fil_travail: list[int] = []
    fil_rendu: list[int] = []
    planifies: list = []

    def travail():
        fil_travail.append(threading.current_thread().ident)
        return "ok"

    def rendre(resultat):
        fil_rendu.append(threading.current_thread().ident)
        assert resultat == "ok"

    def planifier(fn):
        planifies.append(fn)

    fil = lancer_hors_fil(travail, rendre, planifier=planifier)
    fil.join(timeout=2)
    assert not fil.is_alive()
    assert fil_travail
    assert fil_travail[0] != threading.current_thread().ident
    assert fil_rendu == []
    assert planifies
    planifies[0]()
    assert fil_rendu
    assert fil_rendu[0] == threading.current_thread().ident


def test_blocs_couvrent_les_quatre_services_et_leurs_variables():
    from native.presence.reglages_ui import BLOCS

    ids = [bloc["id"] for bloc in BLOCS]
    assert ids == [
        "modele_local",
        "cles",
        "outil_codex",
        "outil_claude",
        "codex",
        "claude",
        "brain_distant",
        "jev",
        "recherche",
    ]
    par_id = {bloc["id"]: bloc["cles"] for bloc in BLOCS}
    assert par_id["modele_local"] == ()
    assert par_id["outil_codex"] == ()
    assert par_id["outil_claude"] == ()
    assert par_id["codex"] == ("CODEX_BRIDGE_URL", "CODEX_BRIDGE_TOKEN")
    assert par_id["claude"] == ("CLI_BRIDGE_URL", "CLI_BRIDGE_TOKEN")
    assert par_id["brain_distant"] == (
        "BRAIN_MODEL",
        "BRAIN_API_ENDPOINT",
        "BRAIN_API_KEY",
    )
    assert par_id["jev"] == ("TYPESAFE_MODEL", "TYPESAFE_API_KEY")
    assert par_id["recherche"] == ()
    assert par_id["cles"] == ()
    assert ids.index("brain_distant") > ids.index("outil_claude")
    assert ids.index("brain_distant") > ids.index("codex")
    assert ids.index("modele_local") < ids.index("outil_codex")
    assert ids.index("cles") < ids.index("outil_codex")
    assert ids.index("brain_distant") < ids.index("jev")


def test_libelles_jev_modele_francais(monkeypatch):
    monkeypatch.delenv("HA_LANG", raising=False)
    monkeypatch.delenv("HYPER_AMBIENT_LANG", raising=False)
    from src.i18n import t

    assert t("reglages.champ.TYPESAFE_MODEL").startswith("Nom du modèle")
    assert "TYPESAFE_MODEL" in t("reglages.champ.TYPESAFE_MODEL")
    assert "jev-latest" in t("reglages.champ.TYPESAFE_MODEL_exemple")
    assert t("reglages.champ.TYPESAFE_MODEL") != t("reglages.champ.BRAIN_MODEL")


def test_categories_regroupent_les_blocs():
    from native.presence.reglages_ui import BLOCS, CATEGORIES

    assert [categorie["id"] for categorie in CATEGORIES] == [
        "machine",
        "outils",
        "distants",
    ]
    plat = [bloc_id for categorie in CATEGORIES for bloc_id in categorie["blocs"]]
    assert plat == [bloc["id"] for bloc in BLOCS]
    assert CATEGORIES[0]["blocs"] == ("modele_local", "cles")
    assert CATEGORIES[1]["blocs"] == (
        "outil_codex",
        "outil_claude",
        "codex",
        "claude",
    )
    assert CATEGORIES[2]["blocs"] == ("brain_distant", "jev", "recherche")


def test_blocs_portent_un_libelle_donnees():
    from src.i18n import t

    from native.presence.reglages_ui import BLOCS, libelle_donnees, sortie_du_bloc

    attendu_sortie = {
        "modele_local": False,
        "cles": False,
        "outil_codex": False,
        "outil_claude": False,
        "codex": False,
        "claude": False,
        "brain_distant": True,
        "jev": True,
        "recherche": True,
    }
    for bloc in BLOCS:
        assert sortie_du_bloc(bloc) is attendu_sortie[bloc["id"]], bloc["id"]
        assert "donnees" in bloc
        texte = libelle_donnees(bloc)
        assert texte.startswith("Données"), bloc["id"]
        assert t(bloc["donnees"]) == texte


def test_blocs_portent_un_marqueur_de_sortie():
    from native.presence.reglages_ui import BLOCS, sortie_du_bloc

    attendu = {
        "modele_local": False,
        "cles": False,
        "outil_codex": False,
        "outil_claude": False,
        "codex": False,
        "claude": False,
        "brain_distant": True,
        "jev": True,
        "recherche": True,
    }
    for bloc in BLOCS:
        assert sortie_du_bloc(bloc) is attendu[bloc["id"]], bloc["id"]
        assert "sortie" in bloc


def test_libelles_donnees_anglais_commencent_par_data(monkeypatch):
    monkeypatch.delenv("HYPER_AMBIENT_LANG", raising=False)
    monkeypatch.setenv("HA_LANG", "en")
    from native.presence.reglages_ui import BLOCS, libelle_donnees
    from src.i18n import t

    for bloc in BLOCS:
        texte = libelle_donnees(bloc)
        assert texte.startswith("Data"), bloc["id"]
        assert t(bloc["donnees"]) == texte
    assert t("reglages.brain_titre") == "Remote model"
    assert t("reglages.champ.BRAIN_MODEL").startswith("Model name")
    assert "BRAIN_MODEL" in t("reglages.champ.BRAIN_MODEL")
    assert t("reglages.champ.TYPESAFE_MODEL").startswith("Model name")
    assert "TYPESAFE_MODEL" in t("reglages.champ.TYPESAFE_MODEL")
    assert "jev-latest" in t("reglages.champ.TYPESAFE_MODEL_exemple")
    assert t("reglages.verifier_aide").lower().startswith("check")


def test_enregistrer_passe_par_poser_reglages(tmp_path):
    from native.presence.reglages_ui import enregistrer_saisie

    chemin = _env(tmp_path, f"BRAIN_MODEL=avant\nBRAIN_API_KEY={_FAUX_JETON}\n")
    ecrits = enregistrer_saisie(
        chemin,
        {
            "BRAIN_MODEL": "apres",
            "BRAIN_API_KEY": "",
            "CODEX_BRIDGE_URL": "http://exemple.invalid/ask",
        },
        {"BRAIN_API_KEY": _FAUX_JETON},
    )
    lus = module_reglages.lire_reglages(chemin)
    assert lus["BRAIN_MODEL"] == "apres"
    assert lus["BRAIN_API_KEY"] == _FAUX_JETON
    assert lus["CODEX_BRIDGE_URL"] == "http://exemple.invalid/ask"
    assert "BRAIN_API_KEY" not in ecrits


def test_poser_reglages_ecrit_typesafe_model(tmp_path):
    from native.presence.reglages_ui import enregistrer_saisie

    chemin = _env(tmp_path, f"TYPESAFE_API_KEY={_FAUX_JETON}\n")
    ecrits = enregistrer_saisie(
        chemin,
        {"TYPESAFE_MODEL": "jev-autre", "TYPESAFE_API_KEY": ""},
        {"TYPESAFE_API_KEY": _FAUX_JETON},
    )
    lus = module_reglages.lire_reglages(chemin)
    assert lus["TYPESAFE_MODEL"] == "jev-autre"
    assert lus["TYPESAFE_API_KEY"] == _FAUX_JETON
    assert ecrits["TYPESAFE_MODEL"] == "jev-autre"
    assert "TYPESAFE_API_KEY" not in ecrits


# ---------------------------------------------------------------------------
# Fenêtre Tk
# ---------------------------------------------------------------------------


def test_fenetre_a_quatre_blocs_et_champs_masques(tmp_path):
    tk, racine = _racine_tk()

    from native.presence.reglages_ui import FenetreReglages

    chemin = _env(
        tmp_path,
        f"BRAIN_API_ENDPOINT={_FAUX_URL}\n"
        f"BRAIN_MODEL={_FAUX_MODELE}\n"
        f"BRAIN_API_KEY={_FAUX_JETON}\n",
    )
    try:
        fenetre = FenetreReglages(racine, chemin)
        racine.update_idletasks()
        textes = " ".join(_textes_widgets(fenetre.fenetre))
        liste = _textes_widgets(fenetre.fenetre)
        assert "Renfort" not in textes
        assert "Modèle distant" in textes
        assert "optionnel" in textes.lower()
        assert "Claude Pro" in textes
        assert "ChatGPT Plus" in textes
        assert "Codex" in textes
        assert "Claude" in textes
        assert "JeV" in textes
        assert "TypeSafe" in textes
        assert "Sur votre machine" in textes
        assert "Vos outils, vos abonnements" in textes
        assert "Services distants" in textes
        assert "Données locales" in textes
        assert "Données envoyées" in textes
        assert "sort de votre machine" not in textes.lower()
        assert "BRAIN_MODEL" in textes
        assert "TYPESAFE_MODEL" in textes
        assert "jev-latest" in textes
        assert fenetre.champs["TYPESAFE_MODEL"].get() == ""
        assert "cinq secondes" in textes
        assert ".env.local" in textes
        assert "fortement recommandé" in textes
        assert "raisonnement" in textes
        assert _FAUX_JETON not in textes
        assert _FAUX_SUFFIXE in textes
        assert fenetre.champs["BRAIN_API_ENDPOINT"].get() == _FAUX_URL
        assert fenetre.champs["BRAIN_MODEL"].get() == _FAUX_MODELE
        assert fenetre.champs["BRAIN_API_KEY"].get() == ""
        assert str(fenetre.champs["BRAIN_API_KEY"].cget("show"))
        assert str(fenetre.champs["CODEX_BRIDGE_TOKEN"].cget("show"))
        assert str(fenetre.champs["CLI_BRIDGE_TOKEN"].cget("show"))
        assert str(fenetre.champs["TYPESAFE_API_KEY"].cget("show"))
        assert isinstance(fenetre.fenetre, tk.Toplevel)
        assert fenetre.fenetre.grab_current() is None
        assert "ne collecte" in textes.lower()
        assert fenetre.marqueurs_confidentialite["modele_local"] is False
        assert fenetre.marqueurs_confidentialite["cles"] is False
        assert fenetre.marqueurs_confidentialite["brain_distant"] is True
        assert fenetre.marqueurs_confidentialite["outil_codex"] is False
        assert fenetre.marqueurs_confidentialite["outil_claude"] is False
        assert fenetre.marqueurs_confidentialite["codex"] is False
        assert fenetre.marqueurs_confidentialite["claude"] is False
        assert fenetre.marqueurs_confidentialite["jev"] is True
        assert fenetre.marqueurs_confidentialite["recherche"] is True
        assert "modele_local" not in fenetre.boutons_verifier
        assert "recherche" not in fenetre.boutons_verifier
        assert "cles" not in fenetre.boutons_verifier

        def _idx(fragment: str) -> int:
            for indice, texte in enumerate(liste):
                if fragment in texte:
                    return indice
            raise AssertionError(fragment)

        assert _idx("Sur votre machine") < _idx("Modèle local")
        assert _idx("Modèle local") < _idx("Clés et réglages")
        assert _idx("Clés et réglages") < _idx("Vos outils, vos abonnements")
        assert _idx("Vos outils, vos abonnements") < _idx("Pont Codex")
        assert _idx("Pont Claude") < _idx("Services distants")
        assert _idx("Services distants") < _idx("Modèle distant")
        assert _idx("Nom du modèle (BRAIN_MODEL)") < _idx("Adresse du modèle")
        assert _idx("JeV (TypeSafe AI)") < _idx("Nom du modèle (TYPESAFE_MODEL)")
        assert _idx("Nom du modèle (TYPESAFE_MODEL)") < _idx("Clé JeV")
    finally:
        racine.destroy()


def test_verifier_desactive_le_bouton_et_rend_la_pastille(tmp_path):
    tk, racine = _racine_tk()

    from native.presence.reglages_ui import FenetreReglages

    pret = threading.Event()
    go = threading.Event()
    fil_sonde: list[int] = []

    async def sonder_codex(url, jeton, client=None):
        fil_sonde.append(threading.current_thread().ident)
        pret.set()
        go.wait(2)
        return Sonde("codex", True, "Codex repond.", 12.0)

    chemin = _env(tmp_path, f"CODEX_BRIDGE_TOKEN={_FAUX_JETON}\n")
    try:
        fenetre = FenetreReglages(
            racine,
            chemin,
            sondes={"codex": sonder_codex},
        )
        racine.update_idletasks()
        bouton = fenetre.boutons_verifier["codex"]
        bouton.invoke()
        racine.update()
        assert pret.wait(2)
        assert str(bouton.cget("state")) == "disabled"
        assert "verifie" in bouton.cget("text").lower().replace("é", "e")
        racine.update()
        assert fil_sonde
        assert fil_sonde[0] != threading.current_thread().ident
        go.set()
        _pomper(
            racine,
            lambda: str(bouton.cget("state")) != "disabled",
        )
        assert "Codex repond" in fenetre.details["codex"].cget("text")
        assert fenetre.pastilles["codex"]["ok"] is True
    finally:
        go.set()
        racine.destroy()


def test_verifier_pastille_rouge_sur_echec(tmp_path):
    tk, racine = _racine_tk()

    from native.presence.reglages_ui import FenetreReglages

    async def sonder_jev(cle, client=None, modele=None):
        return Sonde("jev", False, "JeV ne repond pas.", None)

    try:
        fenetre = FenetreReglages(
            racine,
            tmp_path / ".env.local",
            sondes={"jev": sonder_jev},
        )
        racine.update_idletasks()
        fenetre.boutons_verifier["jev"].invoke()
        _pomper(
            racine,
            lambda: "ne repond pas" in fenetre.details["jev"].cget("text"),
        )
        assert fenetre.pastilles["jev"]["ok"] is False
        assert ".env.local" in fenetre.ligne_statut.cget("text")
    finally:
        racine.destroy()


def test_tout_verifier_appelle_sonder_tout(tmp_path):
    tk, racine = _racine_tk()

    from native.presence.reglages_ui import FenetreReglages

    recu: list[dict] = []

    async def tout(reglages, client=None):
        recu.append(dict(reglages))
        return [
            Sonde("brain_distant", True, "Le modele distant repond.", 1.0),
            Sonde("codex", False, "Codex ne repond pas.", None),
            Sonde("claude", False, "Claude ne repond pas.", None),
            Sonde("jev", True, "JeV repond.", 2.0),
        ]

    chemin = _env(tmp_path, f"BRAIN_API_KEY={_FAUX_JETON}\nBRAIN_MODEL={_FAUX_MODELE}\n")
    try:
        fenetre = FenetreReglages(racine, chemin, sondes={"tout": tout})
        racine.update_idletasks()
        fenetre.bouton_tout.invoke()
        _pomper(racine, lambda: bool(recu) and fenetre.pastilles["brain_distant"]["ok"] is True)
        assert recu
        assert recu[0]["BRAIN_MODEL"] == _FAUX_MODELE
        assert recu[0]["BRAIN_API_KEY"] == _FAUX_JETON
        assert fenetre.pastilles["codex"]["ok"] is False
        assert fenetre.pastilles["jev"]["ok"] is True
    finally:
        racine.destroy()


def test_enregistrer_depuis_la_fenetre_ecrit_sans_reeecrire_la_cle(tmp_path):
    tk, racine = _racine_tk()

    from native.presence.reglages_ui import FenetreReglages

    chemin = _env(
        tmp_path,
        f"BRAIN_MODEL=avant\nBRAIN_API_KEY={_FAUX_JETON}\n",
    )
    try:
        fenetre = FenetreReglages(racine, chemin)
        racine.update_idletasks()
        fenetre.champs["BRAIN_MODEL"].delete(0, tk.END)
        fenetre.champs["BRAIN_MODEL"].insert(0, "apres")
        fenetre.bouton_enregistrer.invoke()
        racine.update_idletasks()
        lus = module_reglages.lire_reglages(chemin)
        assert lus["BRAIN_MODEL"] == "apres"
        assert lus["BRAIN_API_KEY"] == _FAUX_JETON
    finally:
        racine.destroy()


def test_fenetre_utilisable_au_clavier_et_echap_ne_ferme_pas_l_app(tmp_path):
    tk, racine = _racine_tk()

    from native.presence.reglages_ui import FenetreReglages

    try:
        fenetre = FenetreReglages(racine, tmp_path / ".env.local")
        racine.update_idletasks()
        for champ in fenetre.champs.values():
            assert str(champ.cget("takefocus")) in ("1", "true")
        assert str(fenetre.bouton_enregistrer.cget("takefocus")) in ("1", "true")
        assert str(fenetre.bouton_tout.cget("takefocus")) in ("1", "true")
        for bouton in fenetre.boutons_verifier.values():
            assert str(bouton.cget("takefocus")) in ("1", "true")
        assert str(fenetre.bouton_detecter.cget("takefocus")) in ("1", "true")
        fenetre.fenetre.focus_force()
        racine.update()
        fenetre.fenetre.event_generate("<Escape>")
        racine.update()
        assert not fenetre.fenetre.winfo_exists()
        assert racine.winfo_exists()
    finally:
        racine.destroy()


def test_verifier_ne_reeerit_pas_l_url_du_pont(tmp_path):
    """L'URL host.docker.internal reste celle de l'assistante.
    La sonde peut retenter 127.0.0.1 ; le fichier, non."""
    tk, racine = _racine_tk()

    from native.presence.reglages_ui import FenetreReglages

    url_docker = "http://host.docker.internal:8765/ask"

    async def sonder_codex(url, jeton, client=None):
        assert url == url_docker
        return Sonde("codex", True, "Codex repond.", 4.0)

    chemin = _env(
        tmp_path,
        f"CODEX_BRIDGE_URL={url_docker}\nCODEX_BRIDGE_TOKEN={_FAUX_JETON}\n",
    )
    avant = chemin.read_bytes()
    try:
        fenetre = FenetreReglages(
            racine, chemin, sondes={"codex": sonder_codex}
        )
        racine.update_idletasks()
        assert fenetre.champs["CODEX_BRIDGE_URL"].get() == url_docker
        fenetre.boutons_verifier["codex"].invoke()
        _pomper(racine, lambda: fenetre.pastilles["codex"]["ok"] is True)
        assert chemin.read_bytes() == avant
        lus = module_reglages.lire_reglages(chemin)
        assert lus["CODEX_BRIDGE_URL"] == url_docker
    finally:
        racine.destroy()


def test_verifier_un_harnais_appelle_outil_cli_pret(tmp_path):
    tk, racine = _racine_tk()

    from native.presence.reglages_ui import FenetreReglages

    recu: list[str] = []

    def pret(nom):
        recu.append(nom)
        return Sonde("codex", True, "L'outil Codex est installe.", 1.0)

    try:
        fenetre = FenetreReglages(
            racine,
            tmp_path / ".env.local",
            sondes={"outil_codex": pret},
        )
        racine.update_idletasks()
        fenetre.boutons_verifier["outil_codex"].invoke()
        _pomper(racine, lambda: fenetre.pastilles["outil_codex"]["ok"] is True)
        assert recu == ["codex"]
        assert "installe" in fenetre.details["outil_codex"].cget("text")
    finally:
        racine.destroy()


def test_tout_verifier_sonde_aussi_les_harnais(tmp_path):
    tk, racine = _racine_tk()

    from native.presence.reglages_ui import FenetreReglages

    async def tout(reglages, client=None):
        return [
            Sonde("brain_distant", False, "La cle du modele distant n'est pas encore posee.", None),
            Sonde("codex", True, "Codex repond.", 1.0),
            Sonde("claude", True, "Claude repond.", 1.0),
            Sonde("jev", False, "La cle JeV n'est pas encore posee.", None),
        ]

    def pret_codex(nom):
        assert nom == "codex"
        return Sonde("codex", True, "L'outil Codex est installe.", 1.0)

    def pret_claude(nom):
        assert nom == "claude"
        return Sonde("claude", False, "L'outil Claude n'est pas installe.", 1.0)

    try:
        fenetre = FenetreReglages(
            racine,
            tmp_path / ".env.local",
            sondes={
                "tout": tout,
                "outil_codex": pret_codex,
                "outil_claude": pret_claude,
            },
        )
        racine.update_idletasks()
        fenetre.bouton_tout.invoke()
        _pomper(racine, lambda: fenetre.pastilles["outil_codex"]["ok"] is True)
        assert fenetre.pastilles["outil_claude"]["ok"] is False
        assert fenetre.pastilles["codex"]["ok"] is True
    finally:
        racine.destroy()


def test_detecter_abonnements_sonde_les_deux_harnais(tmp_path):
    tk, racine = _racine_tk()

    from native.presence.reglages_ui import FenetreReglages

    recu: list[str] = []

    def pret_codex(nom):
        recu.append(nom)
        return Sonde("codex", True, "L'outil Codex est installe.", 1.0)

    def pret_claude(nom):
        recu.append(nom)
        return Sonde("claude", False, "L'outil Claude n'est pas installe.", 1.0)

    try:
        fenetre = FenetreReglages(
            racine,
            tmp_path / ".env.local",
            sondes={
                "outil_codex": pret_codex,
                "outil_claude": pret_claude,
            },
        )
        racine.update_idletasks()
        assert "abonnement" in fenetre.bouton_detecter.cget("text").lower()
        fenetre.bouton_detecter.invoke()
        _pomper(racine, lambda: fenetre.pastilles["outil_codex"]["ok"] is True)
        assert recu == ["codex", "claude"]
        assert fenetre.pastilles["outil_claude"]["ok"] is False
        assert "installe" in fenetre.details["outil_codex"].cget("text")
        assert "pas installe" in fenetre.details["outil_claude"].cget("text")
    finally:
        racine.destroy()


def test_bouton_reglages_ouvre_depuis_la_fenetre_principale(tmp_path):
    _ouvrir_tk()

    from native.presence.app import Application, analyser_arguments
    from native.presence.onboarding import (
        ConfigurationPresence,
        enregistrer_configuration,
    )

    config = tmp_path / "presence.json"
    enregistrer_configuration(
        ConfigurationPresence(onboarding_termine=True),
        config,
    )
    env_local = _env(tmp_path, f"BRAIN_MODEL={_FAUX_MODELE}\n")
    args = analyser_arguments(["--onboarding", "--config", str(config)])
    try:
        application = Application(args)
    except Exception as exc:
        if exc.__class__.__name__ == "TclError":
            pytest.skip(f"Tk indisponible : {exc}")
        raise
    application.session_lancee = True
    try:
        application._afficher_application()
        application.racine.withdraw()
        application.racine.update_idletasks()
        bouton = application.bouton_reglages
        assert bouton is not None
        assert "Réglages" in bouton.cget("text") or "Reglages" in bouton.cget("text")
        assert str(bouton.cget("takefocus")) in ("1", "true")
        application.ouvrir_reglages(env_local)
        application.racine.update_idletasks()
        assert application.fenetre_reglages is not None
        assert application.fenetre_reglages.fenetre.winfo_exists()
        assert application.fenetre_reglages.fenetre.grab_current() is None
        application.racine.update()
    finally:
        application.fermer()
