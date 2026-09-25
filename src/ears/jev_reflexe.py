"""Evaluation reflexe JeV pour l'entree vocale.

Ce module ne branche rien a l'audio ni au routeur.  Le futur appelant garde le
comportement actuel lorsque :meth:`JevReflexe.evaluate` rend ``None``.  Cela
arrive sans cle, au moindre echec HTTP ou si le budget de 600 ms est depasse.

Un meme ``JevReflexe`` conserve son ``httpx.AsyncClient`` : httpx reutilise
alors la connexion HTTPS (keep-alive) entre les tours.  Les dix-neuf jugements
sont volontairement regroupes dans une seule requete System One.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
import os
import time
import re
import unicodedata
from typing import Any, Mapping, Optional


logger = logging.getLogger(__name__)

JEV_ENDPOINT = "https://api.typesafe.ai/v1/systemone"
JEV_MODEL = "jev-latest"


def modele_jev() -> str:
    """Nom du modèle JeV : ``TYPESAFE_MODEL`` à l'appel, sinon ``jev-latest``.

    Lu à chaque appel, pas à l'import : un changement depuis les réglages
    (ou un monkeypatch de test) prend effet sans recréer le client.
    Une valeur vide ou blanche retombe sur le défaut.
    """
    valeur = (os.getenv("TYPESAFE_MODEL") or "").strip()
    return valeur or JEV_MODEL

MAX_TIMEOUT_MS = 600
PRECHAUFFAGE_TIMEOUT_S = 10.0
# 60 s tient encore (351 ms) ; 90 s expire (601 ms). 40 s reste sous la
# duree de vie mesuree de la connexion chaude (2026-09-20).
INTERVALLE_MAINTIEN_S = 40.0


# Les identifiants sont stables : ils constituent le contrat avec le futur
# branchement EARS, tandis que les instructions restent explicites pour JeV.
QUESTIONS: dict[str, dict[str, Any]] = {
    "assistant_name_spoken": {
        "type": "noul",
        "instructions": (
            "Le nom de l'assistante Hyper Ambient est-il prononce ou "
            "manifestement transcrit dans `transcription` ?"
        ),
        "criteria": {
            "true": (
                "Compter Hyper Ambient et deformations ASR proches : "
                "« hyper ambiant », « hyper ambiance », « hyper ambient », "
                "« super ambiante », « HA », « MOTHER ». Le nom seul suffit."
            ),
            "false": (
                "Aucun de ces noms ou variantes n'est prononce. Ne pas deduire "
                "un nom a partir d'un mot isole comme « ambiance » ou « super »."
            ),
        },
    },
    "direct_interpellation": {
        "type": "noul",
        "instructions": (
            "La personne interpelle-t-elle directement un interlocuteur dans "
            "`transcription` ?"
        ),
        "criteria": {
            "true": (
                "Salutation ou appel direct : « bonjour », « salut », « hey », "
                "« he », « coucou », « allo », « ecoute », « dis-moi », ou "
                "vocatif. Compter une salutation seule : sans contexte contraire, "
                "elle interpelle quelqu'un. Compter aussi une formulation "
                "directement a la deuxieme personne."
            ),
            "false": (
                "Pas d'interpellation : narration, phrase descriptive, reflexion "
                "a voix haute, ou paroles echangees de maniere identifiable entre "
                "d'autres personnes."
            ),
        },
    },
    "request_or_command": {
        "type": "noul",
        "instructions": (
            "La personne formule-t-elle a un interlocuteur une demande, une "
            "question ou un ordre dans `transcription` ?"
        ),
        "criteria": {
            "true": (
                "Question attendant une reponse (« est-ce que tu m'entends ? », "
                "« tu peux… ? »), demande, ou imperatif (« cherche », « arrete », "
                "« attends », « donne-moi »)."
            ),
            "false": (
                "Simple affirmation, narration, lecture, phrase inachevee, ou "
                "question rapportee qui ne demande pas de reponse a l'interlocuteur "
                "present."
            ),
        },
    },
    "third_party_conversation": {
        "type": "noul",
        "instructions": (
            "Les paroles sont-elles clairement destinees a une autre personne "
            "presente ou a un tiers, plutot qu'a l'assistante ?"
        ),
        "criteria": {
            "true": (
                "Conversation identifiable entre humains, consigne a un "
                "collegue/proche, ou message destine a un tiers : par exemple "
                "« je t'envoie le document apres le dejeuner », « bon alors on "
                "disait le module deux »."
            ),
            "false": (
                "Aucun tiers identifiable ; une demande ou salutation pourrait "
                "etre pour l'assistante. Le nom Hyper Ambient/MOTHER/HA n'est "
                "jamais un tiers."
            ),
        },
    },
    "read_broadcast_recited": {
        "type": "noul",
        "instructions": (
            "`transcription` est-elle du contenu lu, diffuse ou recite, plutot "
            "qu'une parole spontanee adressee a l'assistante ?"
        ),
        "criteria": {
            "true": (
                "Television, radio, film, publicite, generique/credits, "
                "narration, lecture a voix haute, dictee, paroles de chanson ou "
                "texte recite : par exemple « et maintenant place au film de la "
                "soiree » ou « Realise par… »."
            ),
            "false": (
                "Parole spontanee a un interlocuteur, meme si elle contient une "
                "salutation, une question ou un ordre."
            ),
        },
    },
    "reported_or_quoted_speech": {
        "type": "noul",
        "instructions": (
            "`transcription` rapporte-t-elle, cite-t-elle ou imite-t-elle des "
            "paroles au lieu de les adresser maintenant a l'assistante ?"
        ),
        "criteria": {
            "true": (
                "Paroles rapportees ou citees, par exemple « il a demande : tu "
                "m'entends ? », « elle a dit bonjour », ou une repetition "
                "d'exemple."
            ),
            "false": (
                "La personne prononce elle-meme, maintenant, la salutation, la "
                "question, la demande ou l'ordre pour obtenir une reponse."
            ),
        },
    },
    "unaddressed_self_talk": {
        "type": "noul",
        "instructions": (
            "La personne parle-t-elle sans s'adresser a aucun interlocuteur ?"
        ),
        "criteria": {
            "true": (
                "Reflexion a voix haute, commentaire personnel, monologue ou "
                "constat sans appel, demande ni destinataire."
            ),
            "false": (
                "Elle interpelle quelqu'un, formule une demande/question/ordre, "
                "parle a un tiers, ou lit/diffuse du contenu."
            ),
        },
    },
    "real_interruption": {
        "type": "noul",
        "instructions": (
            "`transcription` est-elle une interruption reelle de la parole "
            "de l'assistante ?"
        ),
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


# Seuils de addressed_v2. Mesure 2026-09-20 : 0 faux negatif / 24 adressees,
# 0 faux positif / 22 non adressees. Voir nights/2026-09-20-OUT-JEV-QUESTIONS-V2.md.
SEUIL_NOM_PRONONCE = 0.50  # assistant_name_spoken >= : invocation a lui seul
SEUIL_INTERPELLATION = 0.55  # direct_interpellation >=
SEUIL_DEMANDE = 0.50  # request_or_command >=
SEUIL_TIERS = 0.55  # veto si third_party_conversation >=
SEUIL_LU_DIFFUSE = 0.65  # veto si read_broadcast_recited >=
SEUIL_PAROLE_RAPPORTEE = 0.50  # veto si reported_or_quoted_speech >=
SEUIL_MONOLOGUE = 0.70  # veto si unaddressed_self_talk >=


def addressed_v2(a: Mapping[str, Mapping[str, Any]]) -> bool:
    """Nom explicite, ou interpellation/demande sans veto fort.

    Conserve volontairement les salutations seules : le produit prefere
    repondre a un « bonjour » plutot que l'ignorer.
    """

    def s(name: str) -> float:
        return float(a[name]["noul"])

    return s("assistant_name_spoken") >= SEUIL_NOM_PRONONCE or (
        (s("direct_interpellation") >= SEUIL_INTERPELLATION or s("request_or_command") >= SEUIL_DEMANDE)
        and s("third_party_conversation") < SEUIL_TIERS
        and s("read_broadcast_recited") < SEUIL_LU_DIFFUSE
        and s("reported_or_quoted_speech") < SEUIL_PAROLE_RAPPORTEE
        and s("unaddressed_self_talk") < SEUIL_MONOLOGUE
    )


# Le produit s'appelle hyper-ambient ; « MOTHER » reste son ancien nom, encore
# employe a l'oral. Whisper transcrit indifferemment « ambient » et « ambiant ».
_NOMS = (
    # Whisper deforme le nom sur les segments courts. Mesures reelles du
    # 2026-09-20 : « Hyper ambient » rendu « l'ambiance », et
    # « Hyper ambiant » rendu « Super ambiante ». On accepte donc la
    # famille de formes, pas la seule orthographe exacte — mais on exige
    # les DEUX morceaux accoles, pour ne pas se declencher sur un
    # « super » ou une « ambiance » employes seuls.
    r"\b(?:hyper|super|hypere)[\s\'\-]*ambi[ae]n[ct]e?\b",
    r"\bmother\b",
)
_MOTIF_NOM = re.compile("|".join(_NOMS), re.IGNORECASE)


# Duree pendant laquelle elle reste engagee apres avoir ete adressee. Assez
# longue pour enchainer une question apres « Oui ? », assez courte pour ne pas
# transformer la piece en micro ouvert si l'utilisateur s'eloigne.
DUREE_FENETRE_S = 30.0


class FenetreConversation:
    """Une fois nommee, elle reste engagee un moment.

    Mesure du 2026-09-20 contre l'API JeV : « bonjour » (0.31) et « salut »
    (0.25) scorent SOUS une phrase de television en fond (0.26). Aucun seuil ne
    peut donc separer une salutation qui lui est adressee du bruit ambiant, et
    JeV n'a pas tort — un « bonjour » lance dans une piece ne designe
    linguistiquement personne.

    La sortie n'est pas un meilleur seuil mais une memoire courte : on la nomme
    une fois, et ce qui suit lui est adresse. C'est ainsi qu'on parle a
    quelqu'un. Effet de bord utile : pendant la fenetre, aucun appel distant
    n'est necessaire.
    """

    def __init__(self, duree_s: float = DUREE_FENETRE_S) -> None:
        self.duree_s = float(duree_s)
        self._jusqu_a: Optional[float] = None

    def engager(self, maintenant: Optional[float] = None) -> None:
        """Ouvre ou prolonge la fenetre. Chaque tour adresse la repousse."""
        instant = time.monotonic() if maintenant is None else maintenant
        self._jusqu_a = instant + self.duree_s

    def engagee(self, maintenant: Optional[float] = None) -> bool:
        if self._jusqu_a is None:
            return False
        instant = time.monotonic() if maintenant is None else maintenant
        return instant <= self._jusqu_a

    def fermer(self) -> None:
        """Referme immediatement — a appeler quand le mains libres s'eteint."""
        self._jusqu_a = None


def nom_du_produit_prononce(transcription: str) -> bool:
    """True si l'assistante est nommee dans la transcription.

    Dire son nom, c'est s'adresser a elle : l'intention est certaine et se
    verifie en local. Mesure du 2026-09-20 : JeV note « Hyper Ambient » seul a
    0.39, sous tout seuil utilisable — le modele distant juge mal les enonces
    d'un seul mot. On tranche donc ici, sans payer d'appel ni en subir la
    latence.
    """
    if not transcription or not transcription.strip():
        return False
    return bool(_MOTIF_NOM.search(transcription))


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
    # Calibre par la mesure le 2026-09-20 sur 32 phrases (16 adressees,
    # 16 captees autour du micro) : 0.60 est le seuil le plus bas qui ne
    # produit aucun faux positif. A 0.75, neuf phrases adressees sur seize
    # etaient ignorees, dont « tu m'entends ? ». A 0.55, une phrase de
    # television en fond passait — un declenchement parasite coute plus cher
    # qu'une ignorance ponctuelle. Voir nights/2026-09-20-OUT-CALIBRAGE-JEV.md
    noul_true: float = 0.60
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
            noul_true=_env_float("JEV_NOUL_TRUE_THRESHOLD", 0.60, low=0.0, high=1.0),
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
                        "model": modele_jev(),
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

    async def prechauffer(self) -> bool:
        """Paie la poignee TLS hors du budget du tour. Ne leve jamais."""
        if not self._key_at_execution():
            return False
        transport = await self._get_transport()
        if transport is None:
            return False
        try:
            await transport.post(
                self.endpoint,
                json={},
                headers={
                    "Authorization": f"Bearer {self._key_at_execution()}",
                    "Content-Type": "application/json",
                },
                timeout=PRECHAUFFAGE_TIMEOUT_S,
            )
        except Exception:
            logger.debug("JeV prechauffage : connexion non etablie")
            return False
        return True

    async def maintenir(self, intervalle_s: float = INTERVALLE_MAINTIEN_S) -> None:
        """Ping de maintien jusqu'a annulation.

        ``INTERVALLE_MAINTIEN_S`` (40 s) : 60 s tient encore, 90 s expire
        (mesure 2026-09-20).
        """
        try:
            while True:
                await asyncio.sleep(intervalle_s)
                await self.prechauffer()
        except asyncio.CancelledError:
            raise

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
        addressed_to_mother=addressed_v2(answers),
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


# Mots d'appel qui accompagnent le nom sans rien demander (« Hé, hyper ambient ? »).
_APPELS = {"he", "hey", "eh", "oui", "ok", "okay", "dis", "bonjour", "salut", "coucou", "allo"}


def seulement_le_nom(transcription: str) -> bool:
    """True si l'énoncé ne fait que la nommer : elle répond sans cerveau (25/09).

    « Hyper ambiante » seul partait au distant, 4 s pour une réponse générique.
    """
    if not nom_du_produit_prononce(transcription):
        return False
    reste = _MOTIF_NOM.sub(" ", transcription)
    reste = unicodedata.normalize("NFKD", reste.lower())
    reste = "".join(c for c in reste if not unicodedata.combining(c))
    mots = re.sub(r"[^a-z ]", " ", reste).split()
    return all(m in _APPELS for m in mots)
