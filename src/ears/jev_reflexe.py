"""Evaluation reflexe JeV pour l'entree vocale.

Ce module ne branche rien a l'audio ni au routeur.  Le futur appelant garde le
comportement actuel lorsque :meth:`JevReflexe.evaluate` rend ``None``.  Cela
arrive sans cle, au moindre echec HTTP ou si le budget de 600 ms est depasse.

Un meme ``JevReflexe`` conserve son ``httpx.AsyncClient`` : httpx reutilise
alors la connexion HTTPS (keep-alive) entre les tours.  Les treize jugements
sont volontairement regroupes dans une seule requete System One.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
import os
from typing import Any, Mapping, Optional


logger = logging.getLogger(__name__)

JEV_ENDPOINT = "https://api.typesafe.ai/v1/systemone"
JEV_MODEL = "jev-latest"
MAX_TIMEOUT_MS = 600


# Les identifiants sont stables : ils constituent le contrat avec le futur
# branchement EARS, tandis que les instructions restent explicites pour JeV.
QUESTIONS: dict[str, dict[str, Any]] = {
    "addressed_to_mother": {
        "type": "noul",
        "instructions": "La personne parle-t-elle a MOTHER dans `transcription` ?",
        "criteria": {
            "true": "MOTHER est explicitement interpellee ou clairement destinataire.",
            "false": "Conversation autour, texte dicte, ou destinataire incertain.",
        },
    },
    "real_interruption": {
        "type": "noul",
        "instructions": "`transcription` est-elle une interruption reelle de la parole de MOTHER ?",
        "criteria": {
            "true": "Ordre de stopper, attendre, changer ou repondre maintenant.",
            "false": "Simple acquiescement comme « mmh », bruit ou parole sans interruption.",
        },
    },
    "phrase_finished": {
        "type": "noul",
        "instructions": "La phrase de `transcription` semble-t-elle terminee ?",
        "criteria": {
            "true": "Idee ou demande complete.",
            "false": "Debut coupe, hesitations ou suite manifestement attendue.",
        },
    },
    "transcription_uncertain": {
        "type": "noul",
        "instructions": (
            "La transcription `transcription` est-elle douteuse, compte tenu des "
            "indices ASR facultatifs dans `context` ?"
        ),
        "criteria": {
            "true": "Mots incoherents, tronques, ou confiance ASR faible indiquee.",
            "false": "Transcription intelligible, sans indice de doute.",
        },
    },
    "expected_response_length": {
        "type": "choice",
        "instructions": "Quelle longueur de reponse attend la personne pour `transcription` ?",
        "criteria": {
            "one_word": "Reponse tres breve : un mot, une confirmation ou une negation.",
            "few_sentences": "Reponse courte, de quelques phrases.",
            "developed": "Explication ou aide developpee explicitement demandee.",
        },
    },
    "tone": {
        "type": "choice",
        "instructions": "Quel ton de reponse convient le mieux a `transcription` ?",
        "criteria": {
            "calm": "Pose, neutre et rassurant.",
            "cheerful": "Enjoue, leger ou celebrant.",
            "serious": "Factuel et grave.",
            "empathic": "Chaleureux face a une emotion ou une difficulte.",
        },
    },
    "frustration": {
        "type": "score",
        "instructions": "Quel niveau de frustration la personne exprime-t-elle dans `transcription` ?",
        "criteria": [
            "Aucune frustration : ton calme ou neutre.",
            "Legere frustration ou impatience.",
            "Frustration nette.",
            "Forte frustration, colere ou exasperation.",
        ],
    },
    "needs_current_information": {
        "type": "noul",
        "instructions": "`transcription` demande-t-elle une information qui doit etre a jour ?",
        "criteria": {
            "true": "Actualite, prix, meteo, horaire, disponibilite ou autre fait changeant.",
            "false": "Aucune information temporellement sensible demandee.",
        },
    },
    "refers_to_context": {
        "type": "noul",
        "instructions": "`transcription` fait-elle reference au contexte de conversation fourni dans `context` ?",
        "criteria": {
            "true": "Emploie par exemple « ca », « comme avant », « tu te souviens ».",
            "false": "Demande autonome ou aucun contexte fourni.",
        },
    },
    "requests_memory": {
        "type": "noul",
        "instructions": "La personne demande-t-elle explicitement de retenir ou memoriser une information ?",
        "criteria": {
            "true": "Demande explicite de se souvenir, noter ou retenir pour plus tard.",
            "false": "Pas de demande de memorisation.",
        },
    },
    "sensitive_local_action": {
        "type": "noul",
        "instructions": "`transcription` demande-t-elle une action locale sensible ?",
        "criteria": {
            "true": "Action pouvant modifier, supprimer, envoyer, acheter, partager ou affecter l'appareil.",
            "false": "Aucune action locale sensible demandee.",
        },
    },
    "contains_personal_data": {
        "type": "noul",
        "instructions": "`transcription` contient-elle des donnees personnelles identifiantes ?",
        "criteria": {
            "true": "Nom complet, coordonnees, identifiant, adresse, numero ou information personnelle sensible.",
            "false": "Aucune donnee personnelle identifiante visible.",
        },
    },
    "named_harness": {
        "type": "choice",
        "instructions": (
            "Quel harnais la personne nomme-t-elle explicitement dans `transcription` ? "
            "Ne jamais deduire un nom ; choisir none si aucun nom explicite."
        ),
        "criteria": {
            "none": "Aucun harnais n'est explicitement nomme par l'utilisateur.",
            "claude": "L'utilisateur nomme explicitement Claude.",
            "codex": "L'utilisateur nomme explicitement Codex.",
        },
    },
}

_EXPECTED_TYPES = {question_id: question["type"] for question_id, question in QUESTIONS.items()}


def _questions_pour_appel() -> dict[str, dict[str, Any]]:
    """FR par défaut ; ``HA_LANG=en`` envoie les critères en anglais."""
    from src.i18n import questions_jev

    return questions_jev()


def _env_float(name: str, default: float, *, low: float, high: float) -> float:
    """Lit un seuil sans transformer une mauvaise configuration en panne."""
    try:
        value = float(os.getenv(name, str(default)))
    except ValueError:
        return default
    return min(high, max(low, value))


def _env_int(name: str, default: int, *, low: int, high: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return min(high, max(low, value))


@dataclass(frozen=True)
class JevThresholds:
    """Seuils de lecture, ajustables par constructeur ou variables JEV_*.

    ``timeout_ms`` est volontairement plafonne a 600 ms : une valeur configuree
    plus haute ne peut pas retarder le comportement actuel du bouton.
    """

    timeout_ms: int = MAX_TIMEOUT_MS
    noul_true: float = 0.75
    choice_confidence: float = 0.60
    score_confidence: float = 0.60

    def __post_init__(self) -> None:
        object.__setattr__(self, "timeout_ms", min(MAX_TIMEOUT_MS, max(1, int(self.timeout_ms))))
        for field_name in ("noul_true", "choice_confidence", "score_confidence"):
            object.__setattr__(
                self, field_name, min(1.0, max(0.0, float(getattr(self, field_name))))
            )

    @classmethod
    def from_env(cls) -> "JevThresholds":
        return cls(
            timeout_ms=_env_int("JEV_TIMEOUT_MS", MAX_TIMEOUT_MS, low=1, high=MAX_TIMEOUT_MS),
            noul_true=_env_float("JEV_NOUL_TRUE_THRESHOLD", 0.75, low=0.0, high=1.0),
            choice_confidence=_env_float("JEV_CHOICE_CONFIDENCE_THRESHOLD", 0.60, low=0.0, high=1.0),
            score_confidence=_env_float("JEV_SCORE_CONFIDENCE_THRESHOLD", 0.60, low=0.0, high=1.0),
        )


@dataclass(frozen=True)
class JevSignals:
    """Signaux filtres par seuils ; aucun champ ne declenche une action.

    ``named_harness`` rapporte seulement le nom explicitement prononce. Le
    branchement applicatif devra conserver la regle produit : seul l'utilisateur
    decide d'envoyer une tache a un harnais.
    """

    addressed_to_mother: bool
    real_interruption: bool
    phrase_finished: bool
    transcription_uncertain: bool
    expected_response_length: Optional[str]
    tone: Optional[str]
    frustration: Optional[float]
    needs_current_information: bool
    refers_to_context: bool
    requests_memory: bool
    sensitive_local_action: bool
    contains_personal_data: bool
    named_harness: Optional[str]


@dataclass(frozen=True)
class JevEvaluation:
    """Reponse valide et ses signaux ; ``answers`` conserve les probabilites."""

    answers: Mapping[str, Mapping[str, Any]]
    signals: JevSignals


class JevReflexe:
    """Client JeV a connexion HTTPS persistante, injectable pour les tests."""

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        transport: Any = None,
        thresholds: Optional[JevThresholds] = None,
        endpoint: str = JEV_ENDPOINT,
    ) -> None:
        # None signifie « lire la variable a l'execution », pas a l'import.
        self._api_key = api_key
        self._transport = transport
        self._owns_transport = transport is None
        self.thresholds = thresholds if thresholds is not None else JevThresholds.from_env()
        self.endpoint = endpoint

    def _key_at_execution(self) -> str:
        return self._api_key if self._api_key is not None else os.getenv("TYPESAFE_API_KEY", "")

    async def _get_transport(self) -> Any:
        if self._transport is not None:
            return self._transport
        try:
            import httpx
        except ImportError:
            logger.debug("JeV indisponible : client HTTP absent")
            return None

        self._transport = httpx.AsyncClient(
            timeout=self.thresholds.timeout_ms / 1000.0,
            limits=httpx.Limits(max_connections=1, max_keepalive_connections=1, keepalive_expiry=30.0),
        )
        return self._transport

    async def evaluate(
        self, transcription: str, *, context: Optional[Mapping[str, Any]] = None
    ) -> Optional[JevEvaluation]:
        """Evalue une entree ; rend ``None`` pour tout repli silencieux."""
        api_key = self._key_at_execution()
        if not api_key:
            return None

        transport = await self._get_transport()
        if transport is None:
            return None

        state: dict[str, Any] = {"transcription": transcription}
        if context:
            state["context"] = dict(context)
        try:
            # Le timeout du transport peut couvrir chaque phase separement ; le
            # bouton, lui, a un budget total. asyncio.wait_for est donc la
            # barriere definitive, y compris pour un transport injecte.
            response = await asyncio.wait_for(
                transport.post(
                    self.endpoint,
                    json={
                        "state": state,
                        "model": JEV_MODEL,
                        "questions": _questions_pour_appel(),
                    },
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    timeout=self.thresholds.timeout_ms / 1000.0,
                ),
                timeout=self.thresholds.timeout_ms / 1000.0,
            )
        except Exception:
            # Aucun texte utilisateur, URL signee ou cle ne doit sortir des logs.
            logger.debug("JeV indisponible pendant l'evaluation")
            return None

        if getattr(response, "status_code", None) != 200:
            logger.debug("JeV a retourne un statut non utilisable")
            return None
        try:
            payload = response.json()
        except Exception:
            logger.debug("JeV a retourne une reponse illisible")
            return None

        answers = _validated_answers(payload)
        if answers is None:
            logger.debug("JeV a retourne une reponse incomplete")
            return None
        return JevEvaluation(answers=answers, signals=_signals(answers, self.thresholds))

    async def aclose(self) -> None:
        """Ferme uniquement le client cree par cette instance."""
        if self._owns_transport and self._transport is not None:
            close = getattr(self._transport, "aclose", None)
            if close is not None:
                await close()
            self._transport = None

    async def __aenter__(self) -> "JevReflexe":
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.aclose()


def _number(value: Any, *, low: float, high: float) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    value = float(value)
    return value if low <= value <= high else None


def _validated_answers(payload: Any) -> Optional[dict[str, Mapping[str, Any]]]:
    if not isinstance(payload, Mapping) or not isinstance(payload.get("answers"), Mapping):
        return None
    raw_answers = payload["answers"]
    if set(raw_answers) != set(QUESTIONS):
        return None

    validated: dict[str, Mapping[str, Any]] = {}
    for question_id, expected_type in _EXPECTED_TYPES.items():
        answer = raw_answers.get(question_id)
        if not isinstance(answer, Mapping) or answer.get("type") != expected_type:
            return None
        if expected_type == "noul":
            if _number(answer.get("noul"), low=0.0, high=1.0) is None:
                return None
        elif expected_type == "choice":
            allowed = set(QUESTIONS[question_id]["criteria"])
            if answer.get("choice") not in allowed:
                return None
            if _number(answer.get("confidence"), low=0.0, high=1.0) is None:
                return None
        else:  # score
            if _number(answer.get("score"), low=0.0, high=len(QUESTIONS[question_id]["criteria"]) - 1) is None:
                return None
            if _number(answer.get("confidence"), low=0.0, high=1.0) is None:
                return None
        validated[question_id] = answer
    return validated


def _noul(answers: Mapping[str, Mapping[str, Any]], name: str, threshold: float) -> bool:
    return float(answers[name]["noul"]) >= threshold


def _choice(
    answers: Mapping[str, Mapping[str, Any]], name: str, threshold: float
) -> Optional[str]:
    answer = answers[name]
    return str(answer["choice"]) if float(answer["confidence"]) >= threshold else None


def _signals(answers: Mapping[str, Mapping[str, Any]], thresholds: JevThresholds) -> JevSignals:
    """Transforme les sorties typees en suggestions, jamais en actions."""
    return JevSignals(
        addressed_to_mother=_noul(answers, "addressed_to_mother", thresholds.noul_true),
        real_interruption=_noul(answers, "real_interruption", thresholds.noul_true),
        phrase_finished=_noul(answers, "phrase_finished", thresholds.noul_true),
        transcription_uncertain=_noul(answers, "transcription_uncertain", thresholds.noul_true),
        expected_response_length=_choice(answers, "expected_response_length", thresholds.choice_confidence),
        tone=_choice(answers, "tone", thresholds.choice_confidence),
        frustration=(
            float(answers["frustration"]["score"])
            if float(answers["frustration"]["confidence"]) >= thresholds.score_confidence
            else None
        ),
        needs_current_information=_noul(answers, "needs_current_information", thresholds.noul_true),
        refers_to_context=_noul(answers, "refers_to_context", thresholds.noul_true),
        requests_memory=_noul(answers, "requests_memory", thresholds.noul_true),
        sensitive_local_action=_noul(answers, "sensitive_local_action", thresholds.noul_true),
        contains_personal_data=_noul(answers, "contains_personal_data", thresholds.noul_true),
        named_harness=_choice(answers, "named_harness", thresholds.choice_confidence),
    )
