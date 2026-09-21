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


@pytest.fixture(autouse=True)
def voix_sans_reseau(monkeypatch):
    """Les fenêtres de test ne tapent pas Magpie."""
    from src.onboarding.sondes import VOIX_TTS_REPLI, VoixTts

    async def faux(*_a, **_k):
        return VoixTts(VOIX_TTS_REPLI, False)

    monkeypatch.setattr("src.onboarding.sondes.lister_voix_tts", faux)


def _env(tmp_path: Path, texte: str) -> Path:
    chemin = tmp_path / ".env.local"
    chemin.write_bytes(texte.encode("utf-8"))
    return chemin


def _ouvrir_tk():
    """Importe tkinter. Ne crée pas de racine jetable : Tk()+destroy avant
    le vrai ``Tk()`` corrompt Tcl 8.6 sous Python 3.13 (init.tcl, 0x80000003).
    """
    try:
        import tkinter as tk
    except ModuleNotFoundError as exc:
        pytest.skip(f"Tk indisponible : {exc}")
    return tk


def _application_tk(args):
    """Construit ``Application`` sans racine sonde. Retry du premier init.tcl."""
    tk = _ouvrir_tk()
    from native.presence.app import Application

    derniere: Exception | None = None
    for _ in range(3):
        try:
            return Application(args)
        except tk.TclError as exc:
            derniere = exc
    pytest.skip(f"Tk indisponible : {derniere}")


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


def _radios(widget) -> list:
    trouves = []
    try:
        if widget.winfo_class() == "Radiobutton":
            trouves.append(widget)
    except Exception:
        pass
    for enfant in widget.winfo_children():
        trouves.extend(_radios(enfant))
    return trouves


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
        "voix",
        "langue",
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
    assert par_id["voix"] == ("MOUTH_VOICE_NAME", "MOUTH_LANGUAGE")
    assert par_id["langue"] == ()
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
    assert ids.index("modele_local") < ids.index("cles")
    assert ids.index("cles") < ids.index("voix")
    assert ids.index("voix") < ids.index("langue")
    assert ids.index("langue") < ids.index("outil_codex")
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
    assert CATEGORIES[0]["blocs"] == ("modele_local", "cles", "voix", "langue")
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
        "voix": False,
        "langue": False,
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
        "voix": False,
        "langue": False,
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


def test_fenetre_a_quatre_blocs_et_champs_masques(tmp_path, racine_tk):
    tk, racine = racine_tk

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
        assert not fenetre.champs["BRAIN_MODEL"].invite_visible
        assert fenetre.champs["BRAIN_API_KEY"].get() == ""
        assert fenetre.champs["BRAIN_API_KEY"].invite_visible
        assert str(fenetre.champs["BRAIN_API_KEY"].cget("show")) == ""
        assert str(fenetre.champs["BRAIN_API_KEY"].cget("state")) == "normal"
        fenetre.champs["BRAIN_API_KEY"].insert(0, "x")
        assert str(fenetre.champs["BRAIN_API_KEY"].cget("show"))
        assert str(fenetre.champs["CODEX_BRIDGE_TOKEN"].cget("show")) == ""
        assert str(fenetre.champs["CLI_BRIDGE_TOKEN"].cget("show")) == ""
        assert str(fenetre.champs["TYPESAFE_API_KEY"].cget("show")) == ""
        assert fenetre.champs["CODEX_BRIDGE_TOKEN"].secret
        assert fenetre.champs["CLI_BRIDGE_TOKEN"].secret
        assert fenetre.champs["TYPESAFE_API_KEY"].secret
        assert isinstance(fenetre.fenetre, tk.Toplevel)
        assert fenetre.fenetre.grab_current() is None
        assert "ne collecte" in textes.lower()
        assert fenetre.marqueurs_confidentialite["modele_local"] is False
        assert fenetre.marqueurs_confidentialite["voix"] is False
        assert fenetre.marqueurs_confidentialite["langue"] is False
        assert fenetre.marqueurs_confidentialite["cles"] is False
        assert fenetre.marqueurs_confidentialite["brain_distant"] is True
        assert fenetre.marqueurs_confidentialite["outil_codex"] is False
        assert fenetre.marqueurs_confidentialite["outil_claude"] is False
        assert fenetre.marqueurs_confidentialite["codex"] is False
        assert fenetre.marqueurs_confidentialite["claude"] is False
        assert fenetre.marqueurs_confidentialite["jev"] is True
        assert fenetre.marqueurs_confidentialite["recherche"] is True
        assert "modele_local" not in fenetre.boutons_verifier
        assert "voix" not in fenetre.boutons_verifier
        assert "langue" not in fenetre.boutons_verifier
        assert "recherche" not in fenetre.boutons_verifier
        assert "cles" not in fenetre.boutons_verifier

        def _idx(fragment: str) -> int:
            for indice, texte in enumerate(liste):
                if fragment in texte:
                    return indice
            raise AssertionError(fragment)

        assert _idx("Sur votre machine") < _idx("Modèle local")
        assert _idx("Modèle local") < _idx("Clés et réglages")
        assert _idx("Clés et réglages") < _idx("Voix")
        assert _idx("Voix") < _idx("Langue")
        assert _idx("Langue") < _idx("Vos outils, vos abonnements")
        assert "Tavily" in textes
        assert "app.tavily.com" in textes
        assert "peu fiable" in textes.lower()
        assert "carte bancaire" in textes.lower() or "carte" in textes.lower()
        assert _idx("Vos outils, vos abonnements") < _idx("Pont Codex")
        assert _idx("Pont Claude") < _idx("Services distants")
        assert _idx("Services distants") < _idx("Modèle distant")
        assert _idx("Nom du modèle (BRAIN_MODEL)") < _idx("Adresse du modèle")
        assert _idx("JeV (TypeSafe AI)") < _idx("Nom du modèle (TYPESAFE_MODEL)")
        assert _idx("Nom du modèle (TYPESAFE_MODEL)") < _idx("Clé JeV")
    finally:
        fenetre.fermer()


def test_verifier_desactive_le_bouton_et_rend_la_pastille(tmp_path, racine_tk):
    tk, racine = racine_tk

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
        fenetre.fermer()


def test_verifier_pastille_rouge_sur_echec(tmp_path, racine_tk):
    tk, racine = racine_tk

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
        fenetre.fermer()


# ---------------------------------------------------------------------------
# Trois états honnêtes à l'écran
# ---------------------------------------------------------------------------


def _couleur_pastille(fenetre, service):
    toile = fenetre._toiles[service]
    items = toile.find_all()
    assert items, "aucune pastille dessinée"
    return str(toile.itemcget(items[-1], "fill"))


def test_les_trois_etats_ont_trois_couleurs_differents(tmp_path, racine_tk):
    """Joignable-et-muet n'est ni un vert ni un rouge : c'est un troisième
    état, et l'œil doit le distinguer sans lire le libellé."""
    from src.onboarding.sondes import (
        ETAT_INJOIGNABLE,
        ETAT_MUET,
        ETAT_REPOND,
    )

    from native.presence.reglages_ui import FenetreReglages

    tk, racine = racine_tk
    cas = {
        "codex": Sonde("codex", True, "Codex a repondu.", 1.0, ETAT_REPOND),
        "claude": Sonde(
            "claude", False, "Le pont Claude est joignable, mais muet.", 1.0, ETAT_MUET
        ),
        "jev": Sonde(
            "jev", False, "JeV ne repond pas.", 1.0, ETAT_INJOIGNABLE
        ),
    }

    async def tout(reglages, client=None):
        return [
            Sonde("brain_distant", False, "Rien n'est pose.", None),
            cas["codex"],
            cas["claude"],
            cas["jev"],
        ]

    try:
        fenetre = FenetreReglages(racine, tmp_path / ".env.local", sondes={"tout": tout})
        racine.update_idletasks()
        fenetre.bouton_tout.invoke()
        _pomper(racine, lambda: fenetre.pastilles["jev"]["ok"] is False)
        vert = _couleur_pastille(fenetre, "codex")
        orange = _couleur_pastille(fenetre, "claude")
        rouge = _couleur_pastille(fenetre, "jev")
        assert len({vert, orange, rouge}) == 3, (vert, orange, rouge)
        from native.presence.reglages_ui import FOND_VITRE
        from native.presence.sante import contraste_relatif

        for nom, couleur in (("vert", vert), ("orange", orange), ("rouge", rouge)):
            ratio = contraste_relatif(couleur, FOND_VITRE)
            assert ratio >= 3.0, (nom, couleur, ratio)
        assert fenetre.pastilles["codex"]["etat"] == ETAT_REPOND
        assert fenetre.pastilles["claude"]["etat"] == ETAT_MUET
        assert fenetre.pastilles["jev"]["etat"] == ETAT_INJOIGNABLE
    finally:
        fenetre.fermer()


def test_un_harnais_joignable_mais_muet_n_est_pas_vert(tmp_path, racine_tk):
    """Le défaut du brief, vu de l'écran : le pont répond en 13 ms, le
    harnais n'a rien dit. Ni vert, ni « injoignable »."""
    from src.onboarding.sondes import ETAT_MUET

    from native.presence.reglages_ui import FenetreReglages, PASTILLE_OK

    tk, racine = racine_tk

    async def sonder_codex(url, jeton, client=None):
        return Sonde(
            "codex",
            False,
            "Le pont Codex est joignable, mais Codex n'a pas donne la reponse attendue.",
            13.0,
            ETAT_MUET,
        )

    chemin = _env(tmp_path, f"CODEX_BRIDGE_TOKEN={_FAUX_JETON}\n")
    try:
        fenetre = FenetreReglages(racine, chemin, sondes={"codex": sonder_codex})
        racine.update_idletasks()
        fenetre.boutons_verifier["codex"].invoke()
        _pomper(racine, lambda: fenetre.details["codex"].cget("text") != "")
        assert fenetre.pastilles["codex"]["ok"] is False
        assert fenetre.pastilles["codex"]["etat"] == ETAT_MUET
        assert _couleur_pastille(fenetre, "codex") != PASTILLE_OK
        assert "joignable" in fenetre.details["codex"].cget("text")
    finally:
        fenetre.fermer()


def test_sonde_sans_etat_explicite_reste_rouge_pas_orange(tmp_path, racine_tk):
    """Une sonde injectée à l'ancienne (quatre arguments) ne doit pas
    hériter d'un état complaisant."""
    from native.presence.reglages_ui import FenetreReglages, PASTILLE_KO

    tk, racine = racine_tk

    async def sonder_jev(cle, client=None, modele=None):
        return Sonde("jev", True, "JeV a repondu.", 1.0)

    try:
        fenetre = FenetreReglages(
            racine, tmp_path / ".env.local", sondes={"jev": sonder_jev}
        )
        racine.update_idletasks()
        fenetre.boutons_verifier["jev"].invoke()
        _pomper(racine, lambda: fenetre.pastilles["jev"]["ok"] is True)
        assert _couleur_pastille(fenetre, "jev") != PASTILLE_KO
    finally:
        fenetre.fermer()


def test_legende_des_trois_etats_est_affichee(tmp_path, racine_tk):
    """Trois couleurs sans légende, c'est trois devinettes."""
    from native.presence.reglages_ui import FenetreReglages

    tk, racine = racine_tk
    try:
        fenetre = FenetreReglages(racine, tmp_path / ".env.local")
        racine.update_idletasks()
        textes = " ".join(_textes_widgets(fenetre.fenetre)).lower()
        for mot in ("vert", "orange", "rouge"):
            assert mot in textes, mot
        assert "joignable" in textes
    finally:
        fenetre.fermer()


def test_aide_verifier_annonce_le_delai_reel_d_un_harnais(tmp_path, racine_tk):
    """L'écran promettait « cinq secondes » ; un harnais met bien plus.
    Une promesse fausse est un échec de démonstration."""
    from src.onboarding.sondes import DELAI_HARNAIS_S, DELAI_S

    from native.presence.reglages_ui import FenetreReglages

    tk, racine = racine_tk
    try:
        fenetre = FenetreReglages(racine, tmp_path / ".env.local")
        racine.update_idletasks()
        textes = " ".join(_textes_widgets(fenetre.fenetre))
        assert "cinq secondes" in textes
        assert str(int(DELAI_S)) == "5"
        assert str(int(DELAI_HARNAIS_S)) in textes
        assert "réellement" in textes
    finally:
        fenetre.fermer()


def test_fermer_annule_le_tic_de_la_file(tmp_path, racine_tk):
    """Une fenêtre fermée ne doit pas laisser son `after` se déclencher sur un
    widget détruit : Tcl remonte « invalid command name …_pomper_file » à
    chaque fermeture, et le bruit finit dans la console de la démo."""
    from native.presence.reglages_ui import FenetreReglages

    tk, racine = racine_tk
    try:
        fenetre = FenetreReglages(racine, tmp_path / ".env.local")
        racine.update_idletasks()
        assert fenetre._apres is not None
        fenetre.fermer()
        assert fenetre._apres is None
        assert fenetre._vivante() is False
        racine.update()
    finally:
        fenetre.fermer()


def test_enregistrer_sans_rien_changer_ne_cree_pas_de_fichier(tmp_path, racine_tk):
    """Installation neuve : ouvrir les réglages puis « Enregistrer » sans
    rien saisir ne doit pas poser de clés vides. Une clé vide dans
    `.env.local` écrase la valeur du conteneur."""
    from native.presence.reglages_ui import FenetreReglages

    tk, racine = racine_tk
    chemin = tmp_path / ".env.local"
    try:
        fenetre = FenetreReglages(racine, chemin)
        racine.update_idletasks()
        fenetre.bouton_enregistrer.invoke()
        racine.update_idletasks()
        assert not chemin.exists(), chemin.read_text(encoding="utf-8")
        assert "enregistr" in fenetre.ligne_statut.cget("text").lower()
    finally:
        fenetre.fermer()


def test_enregistrer_ne_pose_pas_de_cle_vide_a_cote_des_autres(tmp_path, racine_tk):
    from native.presence.reglages_ui import FenetreReglages

    tk, racine = racine_tk
    chemin = _env(tmp_path, "BRAIN_MODEL=modele-avant\n")
    try:
        fenetre = FenetreReglages(racine, chemin)
        racine.update_idletasks()
        fenetre.champs["TYPESAFE_MODEL"].delete(0, tk.END)
        fenetre.champs["TYPESAFE_MODEL"].insert(0, "jev-autre")
        fenetre.bouton_enregistrer.invoke()
        racine.update_idletasks()
        lus = module_reglages.lire_reglages(chemin)
        assert lus["TYPESAFE_MODEL"] == "jev-autre"
        assert lus["BRAIN_MODEL"] == "modele-avant"
        assert "CODEX_BRIDGE_URL" not in lus
        assert "CLI_BRIDGE_URL" not in lus
        assert "BRAIN_API_ENDPOINT" not in lus
        assert "BRAIN_API_KEY" not in lus
    finally:
        fenetre.fermer()


def test_enregistrer_conserve_une_valeur_deja_posee(tmp_path, racine_tk):
    """Ne pas écrire ce qui n'a pas changé ne veut pas dire l'effacer."""
    from native.presence.reglages_ui import FenetreReglages

    tk, racine = racine_tk
    chemin = _env(
        tmp_path,
        f"BRAIN_MODEL=modele-avant\nBRAIN_API_ENDPOINT={_FAUX_URL}\n",
    )
    try:
        fenetre = FenetreReglages(racine, chemin)
        racine.update_idletasks()
        fenetre.champs["BRAIN_MODEL"].delete(0, tk.END)
        fenetre.champs["BRAIN_MODEL"].insert(0, "modele-apres")
        fenetre.bouton_enregistrer.invoke()
        racine.update_idletasks()
        lus = module_reglages.lire_reglages(chemin)
        assert lus["BRAIN_MODEL"] == "modele-apres"
        assert lus["BRAIN_API_ENDPOINT"] == _FAUX_URL
    finally:
        fenetre.fermer()


def test_enregistrer_un_champ_vide_explicitement_le_vide(tmp_path, racine_tk):
    """Un champ prérempli que l'utilisateur efface est une intention :
    la clé repasse à vide, elle n'est pas ignorée."""
    from native.presence.reglages_ui import FenetreReglages

    tk, racine = racine_tk
    chemin = _env(tmp_path, "BRAIN_MODEL=modele-avant\n")
    try:
        fenetre = FenetreReglages(racine, chemin)
        racine.update_idletasks()
        fenetre.champs["BRAIN_MODEL"].delete(0, tk.END)
        fenetre.bouton_enregistrer.invoke()
        racine.update_idletasks()
        assert module_reglages.lire_reglages(chemin)["BRAIN_MODEL"] == ""
    finally:
        fenetre.fermer()


def test_tout_verifier_appelle_sonder_tout(tmp_path, racine_tk):
    tk, racine = racine_tk

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
        fenetre.fermer()


def test_enregistrer_depuis_la_fenetre_ecrit_sans_reeecrire_la_cle(tmp_path, racine_tk):
    tk, racine = racine_tk

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
        fenetre.fermer()


def test_fenetre_utilisable_au_clavier_et_echap_ne_ferme_pas_l_app(tmp_path, racine_tk):
    tk, racine = racine_tk

    from native.presence.reglages_ui import FenetreReglages

    try:
        fenetre = FenetreReglages(racine, tmp_path / ".env.local")
        racine.update_idletasks()
        for champ in fenetre.champs.values():
            if not hasattr(champ, "cget"):
                continue
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
        fenetre.fermer()


def test_verifier_ne_reeerit_pas_l_url_du_pont(tmp_path, racine_tk):
    """L'URL host.docker.internal reste celle de l'assistante.
    La sonde peut retenter 127.0.0.1 ; le fichier, non."""
    tk, racine = racine_tk

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
        fenetre.fermer()


def test_verifier_un_harnais_appelle_outil_cli_pret(tmp_path, racine_tk):
    tk, racine = racine_tk

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
        fenetre.fermer()


def test_tout_verifier_sonde_aussi_les_harnais(tmp_path, racine_tk):
    tk, racine = racine_tk

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
        fenetre.fermer()


def test_detecter_abonnements_sonde_les_deux_harnais(tmp_path, racine_tk):
    tk, racine = racine_tk

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
        fenetre.fermer()


def test_bouton_reglages_ouvre_depuis_la_fenetre_principale(tmp_path):
    _ouvrir_tk()
    from native.presence.app import analyser_arguments
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
    application = _application_tk(args)
    application.session_lancee = True
    try:
        application._afficher_application()
        application.racine.withdraw()
        application.racine.update_idletasks()
        bouton = application.bouton_reglages
        assert bouton is not None
        assert "Réglages" in bouton.cget("text") or "Reglages" in bouton.cget("text")
        assert str(bouton.cget("takefocus")) in ("1", "true")
        textes = " ".join(_textes_widgets(application.conteneur)).lower()
        assert "un retour" not in textes
        assert "feedback" not in textes
        assert getattr(application, "bouton_feedback", None) is None
        application.ouvrir_reglages(env_local)
        application.racine.update_idletasks()
        assert application.fenetre_reglages is not None
        assert application.fenetre_reglages.fenetre.winfo_exists()
        assert application.fenetre_reglages.fenetre.grab_current() is None
        assert application.fenetre_reglages.menu_aide.entrycget(1, "label") == "Feedback"
        application.racine.update()
    finally:
        application.fermer()


def test_couleurs_champ_distinctes_du_panneau():
    from native.presence.reglages_ui import FOND_VITRE, couleurs_champ

    for contraste in (False, True):
        palette = couleurs_champ(contraste)
        assert palette["fond"].lower() != FOND_VITRE.lower()
        assert palette["bord"] != palette["fond"]
        assert palette["focus"] != palette["bord"]
        assert palette["invite"] != palette["encre"]
    assert couleurs_champ(True)["bord"] != couleurs_champ(False)["bord"]
    assert couleurs_champ(True)["focus"] != couleurs_champ(False)["focus"]


def test_libelles_invite_et_feedback_francais(monkeypatch):
    monkeypatch.delenv("HA_LANG", raising=False)
    monkeypatch.delenv("HYPER_AMBIENT_LANG", raising=False)
    from src.i18n import t

    assert t("ui.feedback") == "Feedback"
    assert t("reglages.menu") == "Aide"
    assert t("reglages.invite.BRAIN_API_KEY").startswith("coller")
    assert t("reglages.invite.CODEX_BRIDGE_TOKEN").startswith("coller")
    for cle in (
        "BRAIN_API_KEY",
        "CODEX_BRIDGE_TOKEN",
        "CLI_BRIDGE_TOKEN",
        "TYPESAFE_API_KEY",
    ):
        texte = t(f"reglages.invite.{cle}").lower()
        assert "déjà" not in texte
        assert "posee" not in texte and "posée" not in texte
        assert "****" not in texte
        assert "sk-" not in texte
    assert t("reglages.invite.BRAIN_MODEL").startswith("ex.")
    assert t("reglages.invite.BRAIN_API_ENDPOINT").startswith("ex.")
    assert t("reglages.voix_titre") == "Voix"
    assert "oreille" in t("reglages.voix_aide").lower()
    assert "redemarrage" in t("reglages.voix_aide").lower().replace("é", "e")
    assert t("reglages.voix_repli").lower().startswith("liste de repli") or "repli" in t(
        "reglages.voix_repli"
    ).lower()
    assert t("reglages.accent_titre") == "Accent"
    assert t("reglages.accent_aucun") == "Aucun accent"
    assert t("reglages.accent.en") == "Accent anglais"
    assert t("reglages.accent.es") == "Accent espagnol"
    assert t("reglages.accent.de") == "Accent allemand"
    assert t("reglages.accent.fr") == "Accent français"
    assert t("reglages.accent.it") == "Accent italien"
    assert t("reglages.accent.vi") == "Accent vietnamien"
    assert t("reglages.accent.hi") == "Accent hindi"
    assert "charmante" in t("reglages.accent_compromis").lower()
    assert "comprendre" in t("reglages.accent_compromis").lower()
    assert t("reglages.voix_ecouter") == "Écouter"
    assert t("reglages.renvoi_outil").startswith("Renvoyer vers l'outil")
    assert t("reglages.langue_titre") == "Langue"
    assert "interface" in t("reglages.langue_aide").lower()
    assert "rechargement" in t("reglages.langue_delai").lower()
    assert "modèles" in t("reglages.langue_delai") or "modeles" in t(
        "reglages.langue_delai"
    ).lower().replace("é", "e")
    assert t("reglages.langue.fr") == "Français"
    assert t("reglages.langue.en") == "Anglais"
    assert "Tavily" in t("reglages.recherche_tavily")
    assert "app.tavily.com" in t("reglages.recherche_tavily")
    assert "peu fiable" in t("reglages.recherche_tavily").lower()
    assert "gratuit" in t("reglages.recherche_tavily").lower()
    from native.presence.reglages_ui import url_tavily

    assert url_tavily() == "https://app.tavily.com"


def test_libelles_invite_et_feedback_anglais(monkeypatch):
    monkeypatch.delenv("HYPER_AMBIENT_LANG", raising=False)
    monkeypatch.setenv("HA_LANG", "en")
    from src.i18n import t

    assert t("ui.feedback") == "Feedback"
    assert t("reglages.menu") == "Help"
    assert t("reglages.invite.BRAIN_API_KEY") == "paste a new key"
    assert t("reglages.invite.CODEX_BRIDGE_TOKEN") == "paste a new token"
    assert t("reglages.invite.BRAIN_MODEL").startswith("e.g.")
    assert "already" not in t("reglages.invite.BRAIN_API_KEY").lower()
    assert t("reglages.voix_titre") == "Voice"
    assert "ear" in t("reglages.voix_aide").lower()
    assert "restart" in t("reglages.voix_aide").lower()
    assert t("reglages.accent_titre") == "Voice accent"
    assert t("reglages.accent_aucun") == "No accent"
    assert t("reglages.accent.en") == "English accent"
    assert t("reglages.accent.es") == "Spanish accent"
    assert t("reglages.accent.de") == "German accent"
    assert "charming" in t("reglages.accent_compromis").lower()
    assert "understand" in t("reglages.accent_compromis").lower()
    assert t("reglages.voix_ecouter") == "Listen"
    assert "tool" in t("reglages.renvoi_outil").lower()
    assert t("reglages.langue_titre") == "Language"
    assert "interface" in t("reglages.langue_aide").lower()
    assert "reload" in t("reglages.langue_delai").lower()
    assert t("reglages.langue.fr") == "French"
    assert t("reglages.langue.en") == "English"
    assert "Tavily" in t("reglages.recherche_tavily")
    assert "app.tavily.com" in t("reglages.recherche_tavily")
    assert "unreliable" in t("reglages.recherche_tavily").lower()
    assert "free" in t("reglages.recherche_tavily").lower()
    from native.presence.reglages_ui import url_tavily

    assert url_tavily() == "https://app.tavily.com"


def test_champs_sont_visiblement_editables(tmp_path, racine_tk):
    tk, racine = racine_tk

    from native.presence.reglages_ui import (
        FOND_VITRE,
        FenetreReglages,
        couleurs_champ,
    )

    chemin = _env(tmp_path, f"BRAIN_MODEL={_FAUX_MODELE}\nBRAIN_API_KEY={_FAUX_JETON}\n")
    try:
        fenetre = FenetreReglages(racine, chemin)
        racine.update_idletasks()
        palette = couleurs_champ(False)
        for champ in fenetre.champs.values():
            if not hasattr(champ, "invite_visible"):
                continue
            assert str(champ.cget("relief")).lower() != "flat"
            assert str(champ.cget("bg")).lower() == palette["fond"].lower()
            assert str(champ.cget("bg")).lower() != FOND_VITRE.lower()
            assert int(str(champ.cget("highlightthickness")) or 0) >= 2
            assert str(champ.cget("highlightcolor")).lower() == palette["focus"].lower()
            assert str(champ.cget("state")) == "normal"
            assert str(champ.cget("takefocus")) in ("1", "true")
        secret = fenetre.champs["BRAIN_API_KEY"]
        assert secret.invite_visible
        assert "coller" in secret.texte_affiche().lower()
        assert _FAUX_SUFFIXE in fenetre._suffixes["BRAIN_API_KEY"].cget("text")
        vide = fenetre.champs["TYPESAFE_MODEL"]
        assert vide.invite_visible
        assert vide.get() == ""
        assert "jev-latest" in vide.texte_affiche()
    finally:
        fenetre.fermer()


def _luminance(hexa: str) -> float:
    brut = str(hexa).lstrip("#")
    canaux = []
    for indice in (0, 2, 4):
        canal = int(brut[indice : indice + 2], 16) / 255
        canaux.append(
            canal / 12.92 if canal <= 0.03928 else ((canal + 0.055) / 1.055) ** 2.4
        )
    return 0.2126 * canaux[0] + 0.7152 * canaux[1] + 0.0722 * canaux[2]


def _contraste(avant: str, arriere: str) -> float:
    une, autre = _luminance(avant), _luminance(arriere)
    if une < autre:
        une, autre = autre, une
    return (une + 0.05) / (autre + 0.05)


def test_le_texte_saisi_est_lisible_sur_le_fond_sombre(tmp_path, racine_tk):
    """« Lisible » se mesure. WCAG AA demande 4,5:1 pour du texte normal :
    c'est la différence entre un champ qu'on voit et un champ qu'on devine."""
    from native.presence.reglages_ui import FOND_VITRE, FenetreReglages

    tk, racine = racine_tk
    try:
        for eleve in (False, True):
            fenetre = FenetreReglages(
                racine, tmp_path / ".env.local", contraste=eleve
            )
            racine.update_idletasks()
            for cle, champ in fenetre.champs.items():
                if not hasattr(champ, "poser_valeur"):
                    continue
                champ.poser_valeur("texte de demonstration")
                racine.update_idletasks()
                encre = str(champ.cget("fg"))
                fond = str(champ.cget("bg"))
                ratio = _contraste(encre, fond)
                assert ratio >= 4.5, (eleve, cle, encre, fond, ratio)
                # Le rectangle doit aussi se détacher du panneau.
                bord = str(champ.cget("highlightbackground"))
                assert _contraste(bord, FOND_VITRE) >= 3.0, (cle, bord)
            fenetre.fermer()
            racine.update_idletasks()
    finally:
        fenetre.fermer()


def test_invite_disparait_a_la_premiere_frappe(tmp_path, racine_tk):
    tk, racine = racine_tk

    from native.presence.reglages_ui import FenetreReglages

    try:
        fenetre = FenetreReglages(racine, tmp_path / ".env.local")
        racine.update_idletasks()
        champ = fenetre.champs["TYPESAFE_MODEL"]
        assert champ.invite_visible

        class _Frappe:
            keysym = "j"
            char = "j"
            state = 0

        champ._frappe(_Frappe())
        racine.update()
        assert not champ.invite_visible
        secret = fenetre.champs["TYPESAFE_API_KEY"]
        assert secret.invite_visible
        assert str(secret.cget("show")) == ""
        secret.insert(0, "abcd")
        assert not secret.invite_visible
        assert str(secret.cget("show")) == "*"
        assert secret.get() == "abcd"
    finally:
        fenetre.fermer()


def test_focus_change_la_bordure_du_champ(tmp_path, racine_tk):
    tk, racine = racine_tk

    from native.presence.reglages_ui import FenetreReglages, couleurs_champ

    try:
        fenetre = FenetreReglages(racine, tmp_path / ".env.local")
        racine.update_idletasks()
        palette = couleurs_champ(False)
        champ = fenetre.champs["BRAIN_MODEL"]
        autre = fenetre.champs["BRAIN_API_ENDPOINT"]
        champ.focus_force()
        racine.update()
        assert str(champ.cget("highlightbackground")).lower() == palette["focus"].lower()
        autre.focus_force()
        racine.update()
        assert str(champ.cget("highlightbackground")).lower() == palette["bord"].lower()
    finally:
        fenetre.fermer()


def test_enregistrer_puis_rouvrir_relit_la_saisie(tmp_path, racine_tk):
    tk, racine = racine_tk

    from native.presence.reglages_ui import FenetreReglages

    nouveau_modele = "modele-apres"
    nouveau_secret = "faux-remplacement-abcd"
    chemin = _env(
        tmp_path,
        f"BRAIN_MODEL=avant\nBRAIN_API_KEY={_FAUX_JETON}\n",
    )
    try:
        fenetre = FenetreReglages(racine, chemin)
        racine.update_idletasks()
        fenetre.champs["BRAIN_MODEL"].delete(0, tk.END)
        fenetre.champs["BRAIN_MODEL"].insert(0, nouveau_modele)
        fenetre.champs["BRAIN_API_KEY"].insert(0, nouveau_secret)
        fenetre.bouton_enregistrer.invoke()
        racine.update_idletasks()
        fenetre.fermer()
        racine.update()
        relue = FenetreReglages(racine, chemin)
        racine.update_idletasks()
        assert relue.champs["BRAIN_MODEL"].get() == nouveau_modele
        assert not relue.champs["BRAIN_MODEL"].invite_visible
        assert relue.champs["BRAIN_API_KEY"].get() == ""
        assert relue.champs["BRAIN_API_KEY"].invite_visible
        assert "abcd" in relue._suffixes["BRAIN_API_KEY"].cget("text")
        lus = module_reglages.lire_reglages(chemin)
        assert lus["BRAIN_MODEL"] == nouveau_modele
        assert lus["BRAIN_API_KEY"] == nouveau_secret
        relue.fermer()
    finally:
        fenetre.fermer()


def test_menu_feedback_dans_la_fenetre_reglages(tmp_path, racine_tk):
    tk, racine = racine_tk

    from native.presence.reglages_ui import FenetreReglages

    recu: list[bool] = []
    try:
        fenetre = FenetreReglages(
            racine,
            tmp_path / ".env.local",
            ouvrir_retour=lambda: recu.append(True),
        )
        racine.update_idletasks()
        assert fenetre.barre_menus.entrycget(1, "label") == "Aide"
        assert fenetre.menu_aide.entrycget(1, "label") == "Feedback"
        fenetre.menu_aide.invoke(1)
        assert recu == [True]
    finally:
        fenetre.fermer()


def test_voix_courante_lit_env_local_puis_carte(tmp_path):
    from native.presence.reglages_ui import voix_courante

    carte = tmp_path / "carte.env"
    carte.write_bytes(b"MOUTH_VOICE_NAME=Sofia\n")
    vide = tmp_path / ".env.local"
    vide.write_bytes(b"BRAIN_MODEL=x\n")
    assert voix_courante(vide, carte) == "Sofia"
    pose = tmp_path / "pose.env"
    pose.write_bytes(b"MOUTH_VOICE_NAME=Aria\n")
    assert voix_courante(pose, carte) == "Aria"


def test_accent_courant_lit_env_local_puis_carte(tmp_path):
    from native.presence.reglages_ui import accent_courant

    carte = tmp_path / "carte.env"
    carte.write_bytes(b"MOUTH_LANGUAGE=fr\n")
    vide = tmp_path / ".env.local"
    vide.write_bytes(b"BRAIN_MODEL=x\n")
    assert accent_courant(vide, carte) == "fr"
    pose = tmp_path / "pose.env"
    pose.write_bytes(b"MOUTH_LANGUAGE=en-US\n")
    assert accent_courant(pose, carte) == "en-US"


def test_libelles_accent_pour_un_humain(monkeypatch):
    monkeypatch.delenv("HA_LANG", raising=False)
    monkeypatch.delenv("HYPER_AMBIENT_LANG", raising=False)
    from native.presence.reglages_ui import libelle_accent, options_accent

    options = options_accent(
        ("en-US", "es-ES", "de-DE", "fr-FR", "it-IT", "vi-VN", "hi-IN", "pt-BR"),
        naturel="fr",
    )
    libelles = [libelle for libelle, _code in options]
    codes = [code for _libelle, code in options]
    assert libelles[0] == "Aucun accent"
    assert codes[0] == "fr"
    assert "Accent anglais" in libelles
    assert "en-US" not in libelles
    assert options[libelles.index("Accent anglais")][1] == "en-US"
    assert "Accent espagnol" in libelles
    assert "Accent allemand" in libelles
    assert "Accent français" in libelles
    assert "Accent italien" in libelles
    assert "Accent vietnamien" in libelles
    assert "Accent hindi" in libelles
    assert libelle_accent("pt-BR") == "Accent (pt-BR)"
    assert "phonétique" not in " ".join(libelles).lower()
    assert "phonetique" not in " ".join(libelles).lower()


def test_menu_voix_vient_du_serveur_pas_du_code(tmp_path, racine_tk):
    tk, racine = racine_tk

    from src.onboarding.sondes import VoixTts

    from native.presence.reglages_ui import FenetreReglages

    def lister():
        return VoixTts(("Nova", "Kai"), True, ("en-US", "ja-JP"))

    try:
        fenetre = FenetreReglages(
            racine,
            tmp_path / ".env.local",
            lister_voix=lister,
        )
        racine.update_idletasks()
        _pomper(
            racine,
            lambda: "Nova" in tuple(fenetre.combo_voix.cget("values")),
        )
        valeurs = tuple(fenetre.combo_voix.cget("values"))
        assert "Nova" in valeurs
        assert "Kai" in valeurs
        assert "John" not in valeurs
        assert fenetre.ligne_voix_repli.cget("text") == ""
        _pomper(
            racine,
            lambda: "Accent anglais" in tuple(fenetre.combo_accent.cget("values")),
        )
        accents = tuple(fenetre.combo_accent.cget("values"))
        assert accents[0] == "Aucun accent"
        assert "Accent anglais" in accents
        assert "en-US" not in accents
        assert "ja-JP" not in accents
        assert fenetre.champs["MOUTH_LANGUAGE"].get() == "fr"
    finally:
        fenetre.fermer()


def test_menu_voix_dit_le_repli_si_serveur_muet(tmp_path, racine_tk):
    tk, racine = racine_tk

    from src.onboarding.sondes import VOIX_TTS_REPLI, VoixTts

    from native.presence.reglages_ui import FenetreReglages

    def lister():
        return VoixTts(VOIX_TTS_REPLI, False)

    try:
        fenetre = FenetreReglages(
            racine,
            tmp_path / ".env.local",
            lister_voix=lister,
        )
        racine.update_idletasks()
        _pomper(racine, lambda: bool(fenetre.ligne_voix_repli.cget("text")))
        textes = " ".join(_textes_widgets(fenetre.fenetre))
        assert "Voix" in textes
        assert "repli" in fenetre.ligne_voix_repli.cget("text").lower()
        assert "Sofia" in tuple(fenetre.combo_voix.cget("values"))
        assert fenetre.champs["MOUTH_VOICE_NAME"].get() == "Sofia"
        assert "redemarrage" in textes.lower().replace("é", "e")
        assert "Écouter" in textes
        assert "charmante" in textes.lower()
        assert not fenetre.corps_voix.winfo_ismapped()
    finally:
        fenetre.fermer()


def test_enregistrer_ecrit_la_voix_choisie(tmp_path, racine_tk):
    tk, racine = racine_tk

    from src.onboarding.sondes import VoixTts

    from native.presence.reglages_ui import FenetreReglages

    def lister():
        return VoixTts(("Sofia", "Aria", "Leo"), True)

    chemin = _env(tmp_path, "BRAIN_MODEL=avant\n")
    try:
        fenetre = FenetreReglages(racine, chemin, lister_voix=lister)
        racine.update_idletasks()
        _pomper(racine, lambda: "Aria" in tuple(fenetre.combo_voix.cget("values")))
        fenetre.var_voix.set("Aria")
        fenetre.bouton_enregistrer.invoke()
        racine.update_idletasks()
        lus = module_reglages.lire_reglages(chemin)
        assert lus["MOUTH_VOICE_NAME"] == "Aria"
        assert lus["BRAIN_MODEL"] == "avant"
        assert lus.get("MOUTH_LANGUAGE", "fr") == "fr"
    finally:
        fenetre.fermer()


def test_enregistrer_ecrit_l_accent_choisi(tmp_path, racine_tk):
    tk, racine = racine_tk

    from src.onboarding.sondes import VoixTts

    from native.presence.reglages_ui import FenetreReglages

    def lister():
        return VoixTts(("Sofia", "Aria"), True, ("en-US", "de-DE", "fr-FR"))

    chemin = _env(tmp_path, "BRAIN_MODEL=avant\n")
    try:
        fenetre = FenetreReglages(racine, chemin, lister_voix=lister)
        racine.update_idletasks()
        _pomper(
            racine,
            lambda: "Accent anglais" in tuple(fenetre.combo_accent.cget("values")),
        )
        fenetre.var_accent.set("Accent anglais")
        fenetre.bouton_enregistrer.invoke()
        racine.update_idletasks()
        lus = module_reglages.lire_reglages(chemin)
        assert lus["MOUTH_LANGUAGE"] == "en-US"
        assert lus["BRAIN_MODEL"] == "avant"
        assert lus.get("MOUTH_VOICE_NAME", "Sofia") == "Sofia"
    finally:
        fenetre.fermer()


def test_ecouter_envoie_voix_et_accent(tmp_path, racine_tk):
    tk, racine = racine_tk

    from src.onboarding.sondes import VoixTts

    from native.presence.reglages_ui import FenetreReglages

    recu: list[tuple[str, str, str]] = []

    def lister():
        return VoixTts(("Sofia", "Aria"), True, ("en-US", "de-DE"))

    def jouer(voix: str, langue: str, texte: str) -> bytes:
        recu.append((voix, langue, texte))
        return b"RIFF"

    try:
        fenetre = FenetreReglages(
            racine,
            tmp_path / ".env.local",
            lister_voix=lister,
            jouer_extrait=jouer,
        )
        racine.update_idletasks()
        _pomper(
            racine,
            lambda: "Accent anglais" in tuple(fenetre.combo_accent.cget("values")),
        )
        fenetre.var_voix.set("Aria")
        fenetre.var_accent.set("Accent anglais")
        fenetre.bouton_ecouter.invoke()
        _pomper(racine, lambda: bool(recu))
        assert recu[0][0] == "Aria"
        assert recu[0][1] == "en-US"
        assert recu[0][2].strip()
    finally:
        fenetre.fermer()


def test_url_tavily_extrait_du_libelle(monkeypatch):
    monkeypatch.delenv("HA_LANG", raising=False)
    monkeypatch.delenv("HYPER_AMBIENT_LANG", raising=False)
    from native.presence.reglages_ui import url_tavily

    assert url_tavily() == "https://app.tavily.com"
    assert (
        url_tavily("Compte : https://app.tavily.com — ensuite la clé.")
        == "https://app.tavily.com"
    )
    assert url_tavily("sans adresse") == ""


def test_menu_langue_dans_reglages(tmp_path, racine_tk):
    tk, racine = racine_tk

    from native.presence.reglages_ui import FenetreReglages

    recu: list[str] = []

    try:
        fenetre = FenetreReglages(
            racine,
            tmp_path / ".env.local",
            langue="fr",
            sur_langue=lambda code: recu.append(code),
        )
        racine.update_idletasks()
        assert fenetre.combo_langue is not None
        assert fenetre.var_langue is not None
        textes = " ".join(_textes_widgets(fenetre.fenetre))
        assert "Langue" in textes
        assert "Français" in textes or "Anglais" in textes
        assert "rechargement" in textes.lower() or "modeles" in textes.lower().replace(
            "é", "e"
        )
        assert fenetre.ligne_langue_delai.cget("text")
        fenetre.var_langue.set("Anglais")
        fenetre._appliquer_langue()
        assert "langue" in fenetre.ligne_langue_etat.cget("text").lower()
        _pomper(racine, lambda: recu == ["en"] and not fenetre.ligne_langue_etat.cget("text"))
        assert recu == ["en"]
        assert fenetre.ligne_langue_delai.cget("text")
    finally:
        fenetre.fermer()


def test_lien_tavily_ouvre_l_adresse(tmp_path, racine_tk):
    tk, racine = racine_tk

    from native.presence.reglages_ui import FenetreReglages

    ouvert: list[str] = []
    try:
        fenetre = FenetreReglages(
            racine,
            tmp_path / ".env.local",
            ouvrir_lien=lambda url: ouvert.append(url),
        )
        racine.update_idletasks()
        assert fenetre.lien_tavily is not None
        assert "app.tavily.com" in fenetre.lien_tavily.cget("text")
        fenetre.lien_tavily.invoke()
        assert ouvert == ["https://app.tavily.com"]
    finally:
        fenetre.fermer()


def test_page_principale_sans_selecteur_langue(tmp_path):
    _ouvrir_tk()
    from native.presence.app import analyser_arguments
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
    application = _application_tk(args)
    application.session_lancee = True
    try:
        application._afficher_application()
        application.racine.withdraw()
        application.racine.update_idletasks()
        textes = " ".join(_textes_widgets(application.conteneur))
        assert application.bouton is not None
        assert application.bouton_stop is not None
        assert application.bouton_mains_libres is not None
        assert application.bouton_reglages is not None
        assert _radios(application.conteneur) == []
        assert "Français" not in textes
        assert "English" not in textes
        application.ouvrir_reglages(env_local)
        application.racine.update_idletasks()
        reglages = " ".join(
            _textes_widgets(application.fenetre_reglages.fenetre)
        )
        assert "Langue" in reglages
        assert "Français" in reglages or "Anglais" in reglages
    finally:
        application.fermer()


def test_ouvrir_et_fermer_les_reglages_plusieurs_fois(tmp_path, racine_tk):
    """Même racine Tk, plusieurs ouvertures : le geste utilisateur, pas la suite."""
    tk, racine = racine_tk

    from native.presence.reglages_ui import FenetreReglages

    chemin = tmp_path / ".env.local"
    for _ in range(5):
        fenetre = FenetreReglages(racine, chemin)
        racine.update_idletasks()
        racine.update()
        assert fenetre._vivante()
        fenetre.fermer()
        racine.update()
        assert fenetre._vivante() is False
    assert racine.winfo_exists()


def test_ouvrir_et_fermer_reglages_depuis_l_application(tmp_path):
    """La fenêtre principale survit à cinq ouvertures successives des réglages."""
    _ouvrir_tk()
    from native.presence.app import analyser_arguments
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
    application = _application_tk(args)
    application.session_lancee = True
    try:
        application._afficher_application()
        application.racine.withdraw()
        application.racine.update_idletasks()
        for _ in range(5):
            application.ouvrir_reglages(env_local)
            application.racine.update_idletasks()
            application.racine.update()
            assert application.fenetre_reglages is not None
            assert application.fenetre_reglages._vivante()
            application.fenetre_reglages.fermer()
            application.racine.update()
            assert not application.fenetre_reglages._vivante()
        application.ouvrir_reglages(env_local)
        application.racine.update_idletasks()
        assert application.fenetre_reglages._vivante()
        assert application.racine.winfo_exists()
    finally:
        application.fermer()


def test_case_renvoi_outil_activee_par_defaut(tmp_path, racine_tk):
    tk, racine = racine_tk

    from native.presence.reglages_ui import FenetreReglages

    chemin = tmp_path / ".env.local"
    try:
        fenetre = FenetreReglages(racine, chemin)
        racine.update_idletasks()
        assert fenetre.champs["VOIX_RENVOI_OUTIL"].get() == "1"
        assert int(fenetre.var_renvoi.get()) == 1
        textes = " ".join(_textes_widgets(fenetre.fenetre))
        assert "Renvoyer vers l'outil" in textes or "outil pour le détail" in textes
    finally:
        fenetre.fermer()


def test_enregistrer_desactive_le_renvoi_outil(tmp_path, racine_tk):
    tk, racine = racine_tk

    from native.presence.reglages_ui import FenetreReglages

    chemin = _env(tmp_path, "BRAIN_MODEL=avant\n")
    try:
        fenetre = FenetreReglages(racine, chemin)
        racine.update_idletasks()
        fenetre.var_renvoi.set(0)
        fenetre.bouton_enregistrer.invoke()
        racine.update_idletasks()
        lus = module_reglages.lire_reglages(chemin)
        assert lus["VOIX_RENVOI_OUTIL"] == "0"
        assert lus["BRAIN_MODEL"] == "avant"
    finally:
        fenetre.fermer()

