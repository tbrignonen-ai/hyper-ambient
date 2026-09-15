"""WorldPort — peripherique visuel muet, jamais un cerveau.

Le world n'entend rien et ne parle pas. BRAIN lui envoie des actions et des
evenements texte ; il rend des images. Presence affichera les frames plus
tard : ce module ne depend ni de MOUTH, ni d'EARS, ni du BRAIN, ni de la
fenetre native.

Le processus est separe et optionnel. Il ne demarre jamais si la VRAM libre
est inconnue ou sous le seuil estime (5,5 Go en FULL 480p, T5 sur CPU).
Tant qu'un run nvidia-smi du world seul n'existe pas, `budget()` reste une
estimation — `mesure` vaut False.

Licence des poids vises : CC-BY-NC-SA 4.0. R&D et demo ecole, pas produit.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Optional

MODELE_ID = "robbyant/lingbot-world-v2-1.3b-causal-fast"
LICENCE = "CC-BY-NC-SA-4.0"
T5_DEVICE = "cpu"
LARGEUR = 832
HAUTEUR = 480
PAS_PAR_CHUNK = 4
VRAM_ESTIMEE_MB = 5500.0
PLAFOND_VRAM_MB = 10000.0

ACTION_KEYS = frozenset({"camera", "move", "text_event"})
AUDIO_KEYS = frozenset({"audio", "pcm", "wav", "samples"})

CRITERES_MESURE = (
    "vram_crete_world_seul_mb",
    "images_par_seconde_480p",
    "latence_action_image_ms",
    "ram_hote_t5_cpu_mb",
    "verdict_coloc_world_mouth_piper_reflexe_distant",
)

_NVIDIA_SMI = (
    "nvidia-smi",
    "--query-gpu=memory.free",
    "--format=csv,noheader,nounits",
)


class VramInsuffisante(RuntimeError):
    """VRAM libre sous le seuil : le world ne demarre pas."""


class VramInconnue(RuntimeError):
    """Impossible de lire nvidia-smi : autant ne pas demarrer a l'aveugle."""


class SessionAbsente(RuntimeError):
    """step() sans start(), ou apres stop()."""


class SessionDejaOuverte(RuntimeError):
    """start() pendant qu'une session tourne encore — stop() d'abord."""


class AudioInterdit(ValueError):
    """Le world n'accepte aucun payload audio."""


class ActionInconnue(ValueError):
    """Cle hors de {camera, move, text_event}."""


@dataclass(frozen=True)
class Session:
    prompt: str
    width: int = LARGEUR
    height: int = HAUTEUR
    mute: bool = True
    image: bool = False


@dataclass(frozen=True)
class FrameChunk:
    frames: tuple[bytes, ...]
    width: int = LARGEUR
    height: int = HAUTEUR
    pas: int = PAS_PAR_CHUNK
    mute: bool = True
    audio: None = None


def lire_vram_libre_mb(*, executeur: Optional[Callable[[tuple[str, ...]], str]] = None) -> Optional[float]:
    """Lit la VRAM libre en Mio. None si la commande echoue ou si la sortie est illisible."""
    lancer = executeur or _executer_nvidia_smi
    try:
        brut = lancer(_NVIDIA_SMI)
    except Exception:
        return None
    if brut is None:
        return None
    ligne = str(brut).strip().splitlines()[0] if str(brut).strip() else ""
    ligne = ligne.replace("MiB", "").replace("MB", "").strip()
    try:
        return float(ligne)
    except ValueError:
        return None


def _executer_nvidia_smi(argv: tuple[str, ...]) -> str:
    termine = subprocess.run(argv, check=False, capture_output=True, text=True, timeout=5)
    if termine.returncode != 0:
        raise RuntimeError(termine.stderr or "nvidia-smi")
    return termine.stdout


def verdict_coloc(
    *,
    vram_world_mb: float,
    vram_reste_stack_mb: float,
    plafond_mb: float = PLAFOND_VRAM_MB,
) -> bool:
    """True ssi world + reste de pile tiennent sous le plafond Thomas (10 Go)."""
    return (vram_world_mb + vram_reste_stack_mb) <= plafond_mb


def vers_evenement(chunk: FrameChunk) -> dict[str, Any]:
    """Forme a poser sur le canal de presence, sans jamais la cle `frames`.

    native/presence/app.py traite `frames` comme de l'audio a restituer.
    Le world utilise `images` et le type `world_frame` : le client actuel
    ignore le message, la voix n'est pas polluee. Le dessin viendra plus tard.
    """
    return {
        "type": "world_frame",
        "width": chunk.width,
        "height": chunk.height,
        "pas": chunk.pas,
        "mute": True,
        "images": list(chunk.frames),
    }


class WorldPort:
    """Pilotage muet : start / step / stop / budget. Backend = bouchon par defaut."""

    def __init__(
        self,
        *,
        vram_libre_mb: Optional[float] = None,
        processus_separe: bool = True,
        backend: Optional[Any] = None,
        lanceur: Optional[Callable[[], Any]] = None,
        executeur_vram: Optional[Callable[[tuple[str, ...]], str]] = None,
        vram_estimee_mb: float = VRAM_ESTIMEE_MB,
    ) -> None:
        self.processus_separe = processus_separe
        self._vram_libre_mb = vram_libre_mb
        self._executeur_vram = executeur_vram
        self._vram_estimee_mb = vram_estimee_mb
        self._backend = backend
        self._lanceur = lanceur
        self._enfant: Any = None
        self._session: Optional[Session] = None
        self.derniere_action: dict[str, Any] = {}
        self._mesure: Optional[dict[str, float]] = None

    def start(self, image_or_prompt: str | bytes) -> Session:
        if self._session is not None:
            raise SessionDejaOuverte("stop() avant une nouvelle session")
        prompt, depuis_image = _lire_amorce(image_or_prompt)
        self._exiger_vram()
        if self.processus_separe and self._lanceur is not None:
            self._enfant = self._lanceur()
        self._session = Session(prompt=prompt, image=depuis_image)
        return self._session

    def step(self, action: Mapping[str, Any]) -> FrameChunk:
        if self._session is None:
            raise SessionAbsente("start() d'abord")
        propre = _valider_action(action)
        self.derniere_action = propre
        if self._backend is not None:
            return self._backend.step(propre)
        return FrameChunk(frames=tuple(b"\x00" for _ in range(PAS_PAR_CHUNK)))

    def stop(self) -> None:
        self._session = None
        self._enfant = None
        self.derniere_action = {}

    def budget(self) -> dict[str, Any]:
        if self._mesure is not None:
            return {
                "vram_mb": self._mesure["vram_mb"],
                "fps": self._mesure["fps"],
                "latence_action_ms": self._mesure["latence_action_ms"],
                "ram_hote_mb": self._mesure["ram_hote_mb"],
                "mesure": True,
            }
        return {
            "vram_mb": self._vram_estimee_mb,
            "fps": 0.0,
            "latence_action_ms": 0.0,
            "mesure": False,
        }

    def noter_mesure(
        self,
        *,
        vram_mb: float,
        fps: float,
        latence_action_ms: float,
        ram_hote_mb: float,
    ) -> None:
        self._mesure = {
            "vram_mb": float(vram_mb),
            "fps": float(fps),
            "latence_action_ms": float(latence_action_ms),
            "ram_hote_mb": float(ram_hote_mb),
        }

    def _exiger_vram(self) -> None:
        if self._vram_libre_mb is not None:
            libre = float(self._vram_libre_mb)
        else:
            libre_lu = lire_vram_libre_mb(executeur=self._executeur_vram)
            if libre_lu is None:
                raise VramInconnue("VRAM illisible : world non demarre")
            libre = libre_lu
        if libre < self._vram_estimee_mb:
            raise VramInsuffisante(
                f"VRAM libre {libre:.0f} Mio < seuil {self._vram_estimee_mb:.0f} Mio"
            )


def _lire_amorce(image_or_prompt: str | bytes) -> tuple[str, bool]:
    if isinstance(image_or_prompt, (bytes, bytearray)):
        if not image_or_prompt:
            raise ValueError("image vide")
        return "", True
    texte = str(image_or_prompt).strip()
    if not texte:
        raise ValueError("prompt vide")
    return texte, False


def _valider_action(action: Mapping[str, Any]) -> dict[str, Any]:
    if action is None:
        raise ActionInconnue("action absente")
    cles = set(action)
    audio = cles & AUDIO_KEYS
    if audio:
        raise AudioInterdit(f"audio interdit au world : {sorted(audio)}")
    inconnues = cles - ACTION_KEYS
    if inconnues:
        raise ActionInconnue(f"action inconnue : {sorted(inconnues)}")
    propre: dict[str, Any] = {}
    for cle in ACTION_KEYS:
        if cle in action:
            propre[cle] = action[cle]
    return propre
