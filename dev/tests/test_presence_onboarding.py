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


def test_overlay_importe_hors_windows():
    """La bulle (transparence, nappe, éclair) doit rester importable sous Linux."""
    pytest.importorskip("tkinter")
    from native.presence import overlay as visuel

    assert visuel.COULEUR_TRANSPARENTE == "#010203"
    assert visuel.eclair_allume("escalade") is True
    assert visuel.eclair_allume("repos") is False
    assert visuel.PALETTES["escalade"]["vitesse_rotation"] > visuel.PALETTES["repos"]["vitesse_rotation"]


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
    import tkinter as tk

    from native.presence import overlay as visuel
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
        assert any("Passer" in t for t in textes)

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
        application.bulle.appliquer_etat("repos", niveau=None)
        application.bulle.dessiner()
        formes_orbe = {application.toile.type(i) for i in application.toile.find_withtag("orbe")}
        assert "polygon" in formes_orbe
        assert "oval" in formes_orbe
        assert application.toile.find_withtag("souffle")
        assert application.toile.find_withtag("nappe")
        # La fenêtre app n'est plus chroma-key : le bureau ne doit plus
        # transpercer le panneau (geste trop faible du 17).
        assert str(application.racine.cget("bg")).lower() != visuel.COULEUR_TRANSPARENTE
        try:
            chroma = str(application.racine.attributes("-transparentcolor")).lower()
        except tk.TclError:
            chroma = ""
        assert chroma in ("", "none", "0") or chroma != visuel.COULEUR_TRANSPARENTE
        fond = " ".join(_textes_widgets(application.conteneur)).lower()
        for interdit in ("welcome", "continue", "skip", "settings", "speak", "hide"):
            assert interdit not in fond
    finally:
        application.fermer()


def test_dessiner_orbe_pose_des_formes_qui_bougent():
    _ouvrir_tk()
    import tkinter as tk

    from native.presence import overlay as visuel

    racine = tk.Tk()
    racine.withdraw()
    try:
        toile = tk.Canvas(racine, width=200, height=200)
        visuel.dessiner_orbe(
            toile,
            cx=100,
            cy=100,
            taille=180,
            etat="reflexion",
            palette=visuel.PALETTES["reflexion"],
            angle=40.0,
            souffle=0.6,
            maintenant=1.25,
        )
        ids = toile.find_withtag("orbe")
        types = {toile.type(i) for i in ids}
        assert "polygon" in types
        assert "oval" in types
        assert "arc" in types
        visuel.dessiner_nappe(
            toile,
            largeur=200,
            hauteur=200,
            palette=visuel.PALETTES["repos"],
            maintenant=2.4,
            etat="repos",
        )
        assert toile.find_withtag("nappe")
        assert toile.find_withtag("souffle")
        ids_souffle = toile.find_withtag("souffle")
        assert "oval" in {toile.type(i) for i in ids_souffle}
        remplis = [
            toile.itemcget(i, "fill")
            for i in toile.find_withtag("nappe")
            if toile.itemcget(i, "fill") not in ("", visuel.COULEUR_TRANSPARENTE)
        ]
        assert remplis, "la nappe doit avoir un corps rempli, pas seulement des contours"
        for fill in remplis:
            r, g, b = visuel.vers_rgb(fill)
            assert (r + g + b) / 3.0 >= 40, fill
    finally:
        racine.destroy()


def test_geste_souffle_respire_avec_le_niveau():
    _ouvrir_tk()
    import tkinter as tk

    from native.presence import overlay as visuel

    racine = tk.Tk()
    racine.withdraw()
    try:
        toile = tk.Canvas(racine, width=200, height=200)
        visuel.dessiner_souffle(
            toile,
            cx=100,
            cy=100,
            rayon=40,
            palette=visuel.PALETTES["ecoute"],
            maintenant=0.4,
            etat="ecoute",
            souffle=0.2,
        )
        visuel.dessiner_souffle(
            toile,
            cx=100,
            cy=100,
            rayon=40,
            palette=visuel.PALETTES["ecoute"],
            maintenant=0.4,
            etat="ecoute",
            souffle=0.95,
        )
        ids = toile.find_withtag("souffle")
        assert len(ids) >= 4
        rayons = []
        for i in ids:
            x0, y0, x1, y1 = toile.coords(i)
            rayons.append((x1 - x0) / 2.0)
        assert max(rayons) > min(rayons) + 8
    finally:
        racine.destroy()


def test_orbe_repos_reste_lisible():
    from native.presence import overlay as visuel

    r, g, b = visuel.vers_rgb(visuel.PALETTES["repos"]["coeur"])
    assert (r + g + b) / 3.0 >= 50
    r, g, b = visuel.vers_rgb(visuel.PALETTES["repos"]["lueur"])
    assert (r + g + b) / 3.0 >= 90


def test_overlay_forme_opaque_sur_chroma_key():
    _ouvrir_tk()
    from native.presence import overlay as visuel

    presence = visuel.Presence(
        visuel.analyser_arguments(["--demo", "--taille", "160", "--coin", "haut-gauche"])
    )
    try:
        presence.racine.withdraw()
        presence.appliquer_etat("parole", niveau=0.7, source="demo")
        presence.dessiner()
        assert str(presence.racine.attributes("-transparentcolor")).lower() == "#010203"
        assert float(presence.racine.attributes("-alpha")) >= 0.85
        assert presence.toile.find_withtag("souffle")
        assert presence.toile.find_withtag("orbe")
        assert presence.toile.find_withtag("nappe")
    finally:
        presence.fermer()


def test_nappe_du_champ_reste_visible_autour_de_l_ui(tmp_path):
    """La nappe n'est plus recouverte : une marge vivante autour de la vitre."""
    _ouvrir_tk()
    from native.presence.app import MARGE_NAPPE, Application, analyser_arguments

    args = analyser_arguments(
        ["--onboarding", "--config", str(tmp_path / "presence.json")]
    )
    application = Application(args)
    application.session_lancee = True
    try:
        application.racine.geometry("520x800+80+40")
        application.racine.update_idletasks()
        application.racine.update()
        application._dessiner_champ()
        assert application.toile_fond is not None
        nappe_ids = application.toile_fond.find_withtag("nappe")
        assert nappe_ids
        xs: list[float] = []
        ys: list[float] = []
        for item in nappe_ids:
            coords = application.toile_fond.coords(item)
            xs.extend(coords[0::2])
            ys.extend(coords[1::2])
        assert xs and ys
        racine_w = application.racine.winfo_width()
        racine_h = application.racine.winfo_height()
        assert min(xs) <= MARGE_NAPPE
        assert max(xs) >= racine_w - MARGE_NAPPE
        assert min(ys) <= MARGE_NAPPE
        assert max(ys) >= racine_h - MARGE_NAPPE
        x = application.conteneur.winfo_x()
        y = application.conteneur.winfo_y()
        w = application.conteneur.winfo_width()
        h = application.conteneur.winfo_height()
        assert x >= MARGE_NAPPE - 1
        assert y >= MARGE_NAPPE - 1
        assert x + w <= racine_w - (MARGE_NAPPE - 1)
        assert y + h <= racine_h - (MARGE_NAPPE - 1)
        assert w < racine_w - 20
        assert h < racine_h - 20
    finally:
        application.fermer()


def test_copies_onboarding_restent_en_francais():
    from native.presence.onboarding import (
        LIBELLE_ECLAIR_ALLUME,
        LIBELLE_ECLAIR_ETEINT,
        TEXTE_BIENVENUE,
        TEXTE_MASQUAGE,
        TEXTE_PTT,
    )

    corpus = " ".join(
        (
            TEXTE_BIENVENUE,
            TEXTE_PTT,
            TEXTE_MASQUAGE,
            LIBELLE_ECLAIR_ETEINT,
            LIBELLE_ECLAIR_ALLUME,
            RAPPEL_A11Y,
        )
    )
    for interdit in ("Welcome", "Continue", "Skip", "Settings", "Speak", "Hide"):
        assert interdit not in corpus
