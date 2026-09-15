import json

import pytest

from native.presence.onboarding import (
    ETAPES_WIZARD,
    RAPPEL_A11Y,
    TEXTE_MASQUAGE,
    TEXTE_PTT,
    ConfigurationPresence,
    charger_configuration,
    couleurs_eclair,
    eclair_allume,
    enregistrer_configuration,
    indicateur_distant,
    libelle_eclair,
    normaliser_configuration,
    sequences_tk,
    sommets_eclair,
    statut_pour_etat,
    terminer_onboarding,
)


def test_configuration_absente_declenche_onboarding(tmp_path):
    configuration = charger_configuration(tmp_path / "absent.json")
    assert configuration == ConfigurationPresence()


def test_configuration_invalide_revient_aux_valeurs_sures():
    configuration = normaliser_configuration(
        {"onboarding_termine": "oui", "raccourci_ptt": "Alt+F4"}
    )
    assert configuration.onboarding_termine is False
    assert configuration.raccourci_ptt == "space"


def test_configuration_est_enregistree_et_rechargee(tmp_path):
    chemin = tmp_path / "presence.json"
    attendue = ConfigurationPresence(True, "ctrl-space")
    enregistrer_configuration(attendue, chemin)

    assert charger_configuration(chemin) == attendue
    assert json.loads(chemin.read_text(encoding="utf-8"))["onboarding_termine"] is True


def test_raccourcis_produisent_un_appui_et_un_relachement():
    assert sequences_tk("space") == ("<KeyPress-space>", "<KeyRelease-space>")
    assert sequences_tk("ctrl-space") == (
        "<Control-KeyPress-space>",
        "<Control-KeyRelease-space>",
    )


def test_wizard_couvre_ptt_raccourci_et_masquage():
    assert ETAPES_WIZARD == ("bienvenue", "ptt", "masquage")


def test_saut_onboarding_termine_sans_perdre_le_raccourci():
    actuelle = ConfigurationPresence(onboarding_termine=False, raccourci_ptt="ctrl-space")
    terminee = terminer_onboarding(actuelle)
    assert terminee.onboarding_termine is True
    assert terminee.raccourci_ptt == "ctrl-space"


def test_terminer_onboarding_enregistre_le_raccourci_choisi():
    actuelle = ConfigurationPresence()
    terminee = terminer_onboarding(actuelle, raccourci_ptt="ctrl-space")
    assert terminee == ConfigurationPresence(True, "ctrl-space")


def test_eclair_reste_eteint_tant_que_l_appel_est_local():
    for etat in ("repos", "ecoute", "reflexion", "parole"):
        assert eclair_allume(etat) is False
        assert "local" in libelle_eclair(etat).lower()


def test_eclair_s_allume_quand_le_modele_parle_au_distant():
    assert eclair_allume("escalade") is True
    libelle = libelle_eclair("escalade")
    assert "distant" in libelle.lower()
    assert libelle != libelle_eclair("repos")


def test_indicateur_distant_n_est_pas_de_la_couleur_seule():
    eteint = indicateur_distant("reflexion")
    allume = indicateur_distant("escalade")
    assert eteint["allume"] is False
    assert allume["allume"] is True
    assert "distant" in allume["libelle"].lower()
    assert allume["statut"]
    assert "distant" in allume["statut"].lower()
    assert eteint["couleurs"] != allume["couleurs"]


def test_statut_escalade_explique_l_appel_distant():
    texte = statut_pour_etat("escalade")
    assert texte is not None
    assert "distant" in texte.lower()
    assert statut_pour_etat("repos") is None


def test_sommets_eclair_forment_un_polygone_lisible():
    coords = sommets_eclair(100.0, 80.0, 40.0)
    assert len(coords) >= 12
    assert len(coords) % 2 == 0
    xs = coords[0::2]
    ys = coords[1::2]
    assert min(xs) < 100.0 < max(xs)
    assert min(ys) < 80.0 < max(ys)


def test_couleurs_eclair_allume_sont_plus_claires():
    fill_off, _ = couleurs_eclair(False)
    fill_on, _ = couleurs_eclair(True, pulsation=0.2)
    fill_pulse, _ = couleurs_eclair(True, pulsation=0.9)
    assert fill_off != fill_on
    assert fill_on != fill_pulse


def test_copies_du_wizard_disent_ptt_masquage_et_clavier():
    assert "focus" in TEXTE_PTT.lower()
    assert "barre des tâches" in TEXTE_MASQUAGE
    assert "Tab" in RAPPEL_A11Y
    assert "texte" in RAPPEL_A11Y.lower()


def _textes_widgets(widget) -> list[str]:
    textes: list[str] = []
    try:
        texte = widget.cget("text")
        if texte:
            textes.append(str(texte))
    except Exception:
        pass
    for enfant in widget.winfo_children():
        textes.extend(_textes_widgets(enfant))
    return textes


def _ouvrir_tk():
    import tkinter as tk

    try:
        racine = tk.Tk()
        racine.withdraw()
        racine.destroy()
    except tk.TclError as exc:
        pytest.skip(f"Tk indisponible : {exc}")


def test_dessiner_eclair_pose_un_polygone_allume():
    _ouvrir_tk()
    import tkinter as tk

    from native.presence.overlay import dessiner_eclair

    racine = tk.Tk()
    racine.withdraw()
    try:
        toile = tk.Canvas(racine, width=80, height=80)
        dessiner_eclair(toile, cx=40, cy=40, taille=50, allume=True, maintenant=0.8)
        ids = toile.find_withtag("eclair")
        assert ids
        assert "polygon" in {toile.type(i) for i in ids}
    finally:
        racine.destroy()


def test_wizard_et_eclair_distant_sont_visibles(tmp_path):
    _ouvrir_tk()
    from native.presence.app import Application, analyser_arguments

    args = analyser_arguments(
        ["--onboarding", "--config", str(tmp_path / "presence.json")]
    )
    application = Application(args)
    application.session_lancee = True
    try:
        application.racine.withdraw()
        application.racine.update_idletasks()
        textes = _textes_widgets(application.conteneur)
        assert any("Bienvenue" in t for t in textes)
        assert any("1 sur 3" in t for t in textes)
        assert any("Passer" in t for t in textes)

        application._afficher_reglage_ptt()
        application.racine.update_idletasks()
        textes = _textes_widgets(application.conteneur)
        assert any("2 sur 3" in t for t in textes)
        assert any("Espace" in t for t in textes)
        assert any("Essayer" in t for t in textes)

        application._afficher_masquage()
        application.racine.update_idletasks()
        textes = _textes_widgets(application.conteneur)
        assert any("3 sur 3" in t for t in textes)
        assert any("Masquer" in t for t in textes)

        application._afficher_application()
        application.racine.update_idletasks()
        application._traiter({"type": "etat", "etat": "escalade", "niveau": None})
        assert application.badge is not None
        assert application.badge.etat == "escalade"
        assert "distant" in application.ligne_eclair.cget("text").lower()
        assert "distant" in application.ligne_etat.cget("text").lower()
        application.badge.dessiner()
        assert application.toile_eclair.find_withtag("eclair")
    finally:
        application.fermer()
