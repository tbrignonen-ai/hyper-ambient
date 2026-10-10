"""Thème de Presence : palette, échelle typographique, espacements.

Une seule source pour app.py, reglages_ui.py, onboarding.py et l'accueil
guidé. Aucune dépendance graphique à l'import : la famille système n'est
demandée à Tk qu'au premier appel de ``police()``, une fois la racine créée.

Les palettes animées de la bulle (PALETTES, PALETTES_CONTRASTE) restent dans
overlay.py : ce sont des courbes d'animation, pas des couleurs d'interface.
"""
from __future__ import annotations

import sys

# --- Palette -----------------------------------------------------------------
# Fonds du plus profond au plus clair ; le fond de champ est celui de la bulle
# (overlay.FOND_CHAMP), vérifié par test.
FOND = "#0c1820"
FOND_VITRE = "#102028"
FOND_SURVOL = "#142028"
FOND_CHAMP = "#1c3a4a"
FOND_CHAMP_CONTRASTE = "#2a5060"
BORD = "#2a4a5c"
BORD_CHAMP = "#6a9aac"
BORD_CHAMP_CONTRASTE = "#a8e0f0"
BORD_FOCUS = "#7ec8dc"
BORD_FOCUS_CONTRASTE = "#e8f8fc"

ENCRE = "#d8e4ec"
ENCRE_SOURDE = "#8aa0b0"
ENCRE_FONCEE = "#0c141c"
# Texte indicatif des champs : #7a96a4 n'atteignait que 3,8:1 sur FOND_CHAMP.
ENCRE_INVITE = "#a3b8c6"
ENCRE_INVITE_CONTRASTE = "#b8d0dc"

PASTILLE_OK = "#3dba7a"
PASTILLE_KO = "#d04a4a"
PASTILLE_NEUTRE = "#4a6474"
PASTILLE_MUET = "#d9a441"
MARQUEUR_LOCAL = "#4a8a72"
MARQUEUR_SORTIE = "#b89654"

ALERTE_FOND = "#3a1c1c"
ALERTE_BORD = "#5a2828"

# Éclair d'appel sortant : éteint en local, jaune vers le distant, violet vers
# un harnais (Codex, Claude). Valeurs historiques d'onboarding.py.
ECLAIR_ETEINT = "#1c303c"
ECLAIR_ETEINT_CONTOUR = "#4a6474"
ECLAIR_ETEINT_A11Y = "#8aa8b8"
ECLAIR_ETEINT_A11Y_CONTOUR = "#c8dce4"
ECLAIR_ALLUME = "#ffcc3d"
ECLAIR_ALLUME_CONTOUR = "#ffe9a0"
ECLAIR_PULSE = "#fff4b0"
ECLAIR_PULSE_CONTOUR = "#ffffff"
ECLAIR_HARNAIS = "#b48cff"
ECLAIR_HARNAIS_CONTOUR = "#e2d4ff"
ECLAIR_HARNAIS_PULSE = "#e8dcff"

# Accueil guidé : un harnais est vert, gris ou rouge (onboarding_llm).
COULEURS_HARNAIS = {
    "vert": PASTILLE_OK,
    "gris": "#6b7d88",
    "rouge": PASTILLE_KO,
}

# Paires texte / fond réellement employées pour du texte courant : chacune doit
# tenir le niveau AA (4,5:1). Le test du thème les vérifie toutes.
PAIRES_TEXTE = (
    (ENCRE, FOND),
    (ENCRE, FOND_VITRE),
    (ENCRE, FOND_SURVOL),
    (ENCRE, FOND_CHAMP),
    (ENCRE, FOND_CHAMP_CONTRASTE),
    (ENCRE_SOURDE, FOND),
    (ENCRE_SOURDE, FOND_VITRE),
    (ENCRE_SOURDE, FOND_SURVOL),
    (ENCRE_INVITE, FOND_CHAMP),
    (ENCRE_INVITE_CONTRASTE, FOND_CHAMP_CONTRASTE),
    (ENCRE, ALERTE_FOND),
    (ENCRE, ALERTE_BORD),
    (ENCRE_FONCEE, BORD_FOCUS),
)
SEUIL_AA = 4.5

# --- Échelle typographique ----------------------------------------------------
# Rôle -> (taille en points sous Windows, graisse). Six tailles, pas davantage.
ECHELLE = {
    "affiche": (24, "bold"),
    "titre": (18, "bold"),
    "sous_titre": (13, "bold"),
    "corps": (12, "normal"),
    "corps_fort": (12, "bold"),
    "texte": (11, "normal"),
    "texte_fort": (11, "bold"),
    "petit": (10, "normal"),
    "petit_fort": (10, "bold"),
    "legende": (9, "normal"),
    "lien": (9, "underline"),
}

# Tk compte les points à 72 ppp sous macOS contre 96 sous Windows : sans ce
# point de plus, tout le texte paraît une taille en dessous sur Mac.
BONUS_TAILLE = {"darwin": 1}

# --- Espacements --------------------------------------------------------------
ESPACE = {"xs": 4, "s": 8, "m": 12, "l": 16, "xl": 24}
MARGE_CADRE = ESPACE["xl"]

# --- Police --------------------------------------------------------------------
FAMILLE_WINDOWS = "Segoe UI"
FAMILLE_MAC_REPLI = "Helvetica Neue"
FAMILLE_LINUX_REPLI = "DejaVu Sans"

_famille_systeme: str | None = None


def famille_police(plateforme: str | None = None, famille_systeme: str | None = None) -> str:
    """Segoe UI sous Windows ; ailleurs la police système que Tk rapporte.

    ``famille_systeme`` est la famille de TkDefaultFont (« .AppleSystemUIFont »
    sur un Mac récent). Sans elle, un repli présent sur la plateforme.
    """
    plateforme = plateforme or sys.platform
    if plateforme.startswith("win"):
        return FAMILLE_WINDOWS
    if famille_systeme:
        return famille_systeme
    if plateforme == "darwin":
        return FAMILLE_MAC_REPLI
    return FAMILLE_LINUX_REPLI


def _demander_famille_systeme() -> str | None:
    try:
        import tkinter
        import tkinter.font

        if getattr(tkinter, "_default_root", None) is None:
            return None
        return str(tkinter.font.nametofont("TkDefaultFont").actual("family")) or None
    except Exception:  # pas de Tk, pas d'écran : le repli suffit
        return None


def police(role: str, plateforme: str | None = None) -> tuple:
    """Tuple ``font=`` de Tk pour un rôle de l'échelle."""
    global _famille_systeme
    plateforme = plateforme or sys.platform
    taille, graisse = ECHELLE[role]
    taille += BONUS_TAILLE.get(plateforme, 0)
    if plateforme.startswith("win"):
        famille = FAMILLE_WINDOWS
    else:
        if _famille_systeme is None:
            _famille_systeme = _demander_famille_systeme()
        famille = famille_police(plateforme, _famille_systeme)
    if graisse == "normal":
        return (famille, taille)
    return (famille, taille, graisse)


# --- Contraste (WCAG 2.x) ------------------------------------------------------

def _canal(valeur: float) -> float:
    return valeur / 12.92 if valeur <= 0.03928 else ((valeur + 0.055) / 1.055) ** 2.4


def luminance(hex_couleur: str) -> float:
    brut = hex_couleur.lstrip("#")
    r, v, b = (int(brut[i : i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * _canal(r) + 0.7152 * _canal(v) + 0.0722 * _canal(b)


def contraste(premier: str, second: str) -> float:
    clair, sombre = sorted((luminance(premier), luminance(second)), reverse=True)
    return (clair + 0.05) / (sombre + 0.05)
