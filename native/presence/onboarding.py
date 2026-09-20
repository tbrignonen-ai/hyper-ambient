"""Configuration locale, sans dépendance graphique, de l'onboarding presence."""
from __future__ import annotations

import json
import os
import webbrowser
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

URL_FEEDBACK = "https://github.com/tbrignonen-ai/hyper-ambient/issues/new"


RACCOURCIS = {
    "space": "Espace",
    "ctrl-space": "Ctrl + Espace",
}

ETAPES_WIZARD = ("bienvenue", "mains_libres", "ptt", "masquage")

LIBELLE_ECLAIR_ETEINT = "Modèle local"
LIBELLE_ECLAIR_ALLUME = "Appel distant"

STATUT_APPEL_DISTANT = (
    "Appel distant en cours — le modèle local interroge un modèle distant."
)

TEXTE_BIENVENUE = (
    "Une présence vocale discrète, disponible quand vous la sollicitez. "
    "La lumière respire avec elle. "
    "Trois réglages suffisent : comment parler, quel raccourci, comment masquer."
)

TEXTE_PTT = (
    "Maintenez Parler ou le raccourci choisi, puis relâchez pour envoyer. "
    "Le raccourci ne fonctionne que lorsque cette fenêtre a le focus."
)

TEXTE_MASQUAGE = (
    "Masquer la configuration réduit la fenêtre dans la barre des tâches. "
    "Un clic sur son icône la rappelle. La croix et Échap ferment vraiment l'application."
)

RAPPEL_A11Y = (
    "Tab parcourt les commandes. Entrée active un bouton. "
    "Vous pouvez maintenir Entrée sur Parler. "
    "Transcriptions, réponses et appel distant restent affichés en texte."
)

COULEUR_ECLAIR_ETEINT = "#1c303c"
CONTOUR_ECLAIR_ETEINT = "#4a6474"
COULEUR_ECLAIR_ETEINT_A11Y = "#8aa8b8"
CONTOUR_ECLAIR_ETEINT_A11Y = "#c8dce4"
COULEUR_ECLAIR_ALLUME = "#ffcc3d"
CONTOUR_ECLAIR_ALLUME = "#ffe9a0"
COULEUR_ECLAIR_PULSE = "#fff4b0"
CONTOUR_ECLAIR_PULSE = "#ffffff"


@dataclass(frozen=True)
class ConfigurationPresence:
    onboarding_termine: bool = False
    raccourci_ptt: str = "space"
    langue: str = "fr"
    contraste: bool = False
    mains_libres: bool = False


def chemin_configuration() -> Path:
    """Retourne un chemin utilisateur stable, sans écrire dans le dépôt."""
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if base:
        return Path(base) / "hyper-ambient" / "presence.json"
    return Path.home() / ".hyper-ambient" / "presence.json"


def normaliser_configuration(brut: Mapping[str, Any] | None) -> ConfigurationPresence:
    brut = brut or {}
    raccourci = str(brut.get("raccourci_ptt") or "space")
    if raccourci not in RACCOURCIS:
        raccourci = "space"
    langue = str(brut.get("langue") or "fr").strip().lower().replace("_", "-")
    if langue.startswith("en"):
        langue = "en"
    else:
        langue = "fr"
    return ConfigurationPresence(
        onboarding_termine=brut.get("onboarding_termine") is True,
        raccourci_ptt=raccourci,
        langue=langue,
        contraste=brut.get("contraste") is True,
        mains_libres=brut.get("mains_libres") is True,
    )


def charger_configuration(chemin: Path | None = None) -> ConfigurationPresence:
    cible = chemin or chemin_configuration()
    try:
        brut = json.loads(cible.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return ConfigurationPresence()
    if not isinstance(brut, dict):
        return ConfigurationPresence()
    return normaliser_configuration(brut)


def enregistrer_configuration(
    configuration: ConfigurationPresence, chemin: Path | None = None
) -> Path:
    cible = chemin or chemin_configuration()
    cible.parent.mkdir(parents=True, exist_ok=True)
    temporaire = cible.with_suffix(cible.suffix + ".tmp")
    temporaire.write_text(
        json.dumps(asdict(configuration), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporaire.replace(cible)
    return cible


def sequences_tk(raccourci: str) -> tuple[str, str]:
    """Traduit le choix lisible en événements maintien/relâchement Tk."""
    if raccourci == "ctrl-space":
        return "<Control-KeyPress-space>", "<Control-KeyRelease-space>"
    return "<KeyPress-space>", "<KeyRelease-space>"


def sequences_relache_extra(raccourci: str) -> tuple[str, ...]:
    """Ctrl+Espace : Space relâché sans Ctrl doit aussi déverrouiller le latch."""
    if raccourci == "ctrl-space":
        return ("<KeyRelease-space>",)
    return ()


def terminer_onboarding(
    configuration: ConfigurationPresence,
    raccourci_ptt: str | None = None,
    mains_libres: bool | None = None,
) -> ConfigurationPresence:
    """Clôt le wizard en conservant le raccourci déjà choisi, sauf remplacement."""
    choix = configuration.raccourci_ptt if raccourci_ptt is None else raccourci_ptt
    actif = configuration.mains_libres if mains_libres is None else mains_libres
    return normaliser_configuration(
        {
            "onboarding_termine": True,
            "raccourci_ptt": choix,
            "langue": configuration.langue,
            "contraste": configuration.contraste,
            "mains_libres": actif is True,
        }
    )


def message_options(mains_libres: bool) -> dict[str, Any]:
    """Contrat WS Presence → host-agent : JeV seulement si mains libres."""
    return {"type": "options", "mains_libres": bool(mains_libres)}


def appliquer_langue_presence(
    configuration: ConfigurationPresence,
    environ: dict[str, str] | None = None,
) -> str:
    """HA_LANG / HYPER_AMBIENT_LANG primer ; sinon langue persistée dans presence.json."""
    env = os.environ if environ is None else environ
    if str(env.get("HA_LANG") or "").strip() or str(env.get("HYPER_AMBIENT_LANG") or "").strip():
        from src.i18n import langue

        return langue()
    env["HA_LANG"] = configuration.langue if configuration.langue in {"fr", "en"} else "fr"
    from src.i18n import langue

    return langue()


def url_nouvelle_issue() -> str:
    return URL_FEEDBACK


def ouvrir_feedback(ouvrir: Any | None = None) -> bool:
    """Ouvre une issue GitHub. ``ouvrir`` injectable (tests, pas de navigateur)."""
    cible = url_nouvelle_issue()
    action = webbrowser.open if ouvrir is None else ouvrir
    return bool(action(cible))


def eclair_allume(etat: str) -> bool:
    """L'éclair ne s'allume que lorsque l'appel sort vers un modèle distant."""
    return etat == "escalade"


def ui_presence() -> dict[str, str]:
    from src.i18n import ui

    return ui()


def raccourcis_lisibles() -> dict[str, str]:
    textes = ui_presence()
    return {"space": textes["shortcut"], "ctrl-space": textes["shortcut_ctrl"]}


def libelle_eclair(etat: str) -> str:
    textes = ui_presence()
    if eclair_allume(etat):
        return textes["remote_call"]
    return textes["local_model"]


def statut_pour_etat(etat: str) -> str | None:
    if eclair_allume(etat):
        return ui_presence()["remote_status"]
    return None


def couleurs_eclair(
    allume: bool, pulsation: float = 0.0, a11y: bool = False
) -> tuple[str, str]:
    if not allume:
        if a11y:
            return COULEUR_ECLAIR_ETEINT_A11Y, CONTOUR_ECLAIR_ETEINT_A11Y
        return COULEUR_ECLAIR_ETEINT, CONTOUR_ECLAIR_ETEINT
    if pulsation >= 0.62:
        return COULEUR_ECLAIR_PULSE, CONTOUR_ECLAIR_PULSE
    return COULEUR_ECLAIR_ALLUME, CONTOUR_ECLAIR_ALLUME


def sommets_eclair(cx: float, cy: float, taille: float) -> tuple[float, ...]:
    """Éclair à six sommets, centré, assez grand pour rester lisible à 200 px."""
    echelle = max(16.0, taille * 0.55)
    rel = (
        (0.14, -0.56),
        (-0.28, 0.04),
        (0.02, 0.04),
        (-0.14, 0.56),
        (0.28, -0.04),
        (-0.02, -0.04),
    )
    coords: list[float] = []
    for x, y in rel:
        coords.append(cx + x * echelle)
        coords.append(cy + y * echelle)
    return tuple(coords)


def indicateur_distant(etat: str, *, pulsation: float = 0.0) -> dict[str, Any]:
    allume = eclair_allume(etat)
    fill, contour = couleurs_eclair(allume, pulsation=pulsation)
    return {
        "allume": allume,
        "libelle": libelle_eclair(etat),
        "statut": statut_pour_etat(etat),
        "couleurs": (fill, contour),
    }
