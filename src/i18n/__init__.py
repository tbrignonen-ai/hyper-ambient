"""Langue d'interface Hyper Ambient 0.1.

FR reste le défaut. ``HA_LANG`` / ``HYPER_AMBIENT_LANG`` : ``en`` ou ``en-US``
passent en anglais ; toute autre valeur retombe sur le français.
"""
from __future__ import annotations

import os
from typing import Any

_FR: dict[str, str] = {
    "tools.ask_codex": "Je demande à Codex, ça prend une vingtaine de secondes.",
    "tools.ask_muse": "Je demande son avis à Muse, ça prend une trentaine de secondes.",
    "tools.ask_claude": "Je demande son analyse à Claude.",
    "tools.web_search": "Je cherche ça sur le web.",
    "tools.calculer": "Je calcule ça.",
    "tools.default": "Je consulte un outil.",
    "ui.welcome_title": "Bienvenue",
    "ui.welcome_body": (
        "Une présence vocale discrète, disponible quand vous la sollicitez. "
        "La lumière respire avec elle. "
        "Trois réglages suffisent : comment parler, quel raccourci, comment masquer."
    ),
    "ui.ptt_title": "Appuyez pour parler",
    "ui.ptt_body": (
        "Maintenez Parler ou le raccourci choisi, puis relâchez pour envoyer. "
        "Le raccourci ne fonctionne que lorsque cette fenêtre a le focus."
    ),
    "ui.hide_title": "Masquer la configuration",
    "ui.hide_body": (
        "Masquer la configuration réduit la fenêtre dans la barre des tâches. "
        "Un clic sur son icône la rappelle. La croix et Échap ferment vraiment l'application."
    ),
    "ui.a11y": (
        "Tab parcourt les commandes. Entrée active un bouton. "
        "Vous pouvez maintenir Entrée sur Parler. "
        "Transcriptions, réponses et appel distant restent affichés en texte."
    ),
    "ui.step": "Étape {indice} sur {total}",
    "ui.skip": "Passer",
    "ui.continue": "Continuer",
    "ui.no_recording": "Aucun son n'est enregistré pendant cette configuration.",
    "ui.shortcut_in_app": "Raccourci clavier dans l'application",
    "ui.try_hold": "Essayer : maintenez ici (souris ou Entrée)",
    "ui.hearing": "Je vous entends — relâchez pour envoyer",
    "ui.speak": "Parler",
    "ui.speaking": "Parler…",
    "ui.hide_config": "Masquer la configuration",
    "ui.understood": "Compris",
    "ui.reply": "Réponse",
    "ui.shortcut": "Espace",
    "ui.shortcut_ctrl": "Ctrl + Espace",
    "ui.local_model": "Modèle local",
    "ui.remote_call": "Appel distant",
    "ui.remote_status": (
        "Appel distant en cours — le modèle local interroge un modèle distant."
    ),
    "ui.start": "Commencer",
    "ui.start_and_hide": "Commencer et masquer",
    "ui.shortcut_kept": (
        "Raccourci retenu : {raccourci}. "
        "Pendant un appel distant, l'éclair s'allume et le statut le dit en texte."
    ),
    "ui.channel_not_ready": "Canal pas encore prêt.",
}

_EN: dict[str, str] = {
    "tools.ask_codex": "I'll ask Codex — that takes about twenty seconds.",
    "tools.ask_muse": "I'll ask Muse — that takes about thirty seconds.",
    "tools.ask_claude": "I'll ask Claude for her analysis.",
    "tools.web_search": "I'll look that up on the web.",
    "tools.calculer": "I'll calculate that.",
    "tools.default": "I'll check a tool.",
    "ui.welcome_title": "Welcome",
    "ui.welcome_body": (
        "A quiet voice on this computer, there when you call it. "
        "The light breathes with it. "
        "Three settings: how to talk, which shortcut, how to hide."
    ),
    "ui.ptt_title": "Press to talk",
    "ui.ptt_body": (
        "Hold Talk or your shortcut, then release to send. "
        "The shortcut only works while this window is focused."
    ),
    "ui.hide_title": "Hide the settings",
    "ui.hide_body": (
        "Hiding the settings minimizes the window to the taskbar. "
        "Click its icon to bring it back. The close button and Escape really quit."
    ),
    "ui.a11y": (
        "Tab moves between controls. Enter activates a button. "
        "You can hold Enter on Talk. "
        "Transcripts, replies and remote calls stay visible as text."
    ),
    "ui.step": "Step {indice} of {total}",
    "ui.skip": "Skip",
    "ui.continue": "Continue",
    "ui.no_recording": "No sound is recorded during this setup.",
    "ui.shortcut_in_app": "Keyboard shortcut in the app",
    "ui.try_hold": "Try it: hold here (mouse or Enter)",
    "ui.hearing": "I can hear you — release to send",
    "ui.speak": "Talk",
    "ui.speaking": "Talk…",
    "ui.hide_config": "Hide settings",
    "ui.understood": "Heard",
    "ui.reply": "Reply",
    "ui.shortcut": "Space",
    "ui.shortcut_ctrl": "Ctrl + Space",
    "ui.local_model": "Local model",
    "ui.remote_call": "Remote call",
    "ui.remote_status": (
        "Remote call in progress — the local model is asking a remote one."
    ),
    "ui.start": "Start",
    "ui.start_and_hide": "Start and hide",
    "ui.shortcut_kept": (
        "Shortcut kept: {raccourci}. "
        "During a remote call the lightning bolt lights up and the status says so in text."
    ),
    "ui.channel_not_ready": "Channel not ready yet.",
}

_TABLES = {"fr": _FR, "en": _EN}

QUESTIONS_EN: dict[str, dict[str, Any]] = {
    "addressed_to_mother": {
        "type": "noul",
        "instructions": "Is the person speaking to MOTHER in `transcription`?",
        "criteria": {
            "true": "MOTHER is explicitly addressed or clearly the addressee.",
            "false": "Side conversation, dictated text, or unclear addressee.",
        },
    },
    "real_interruption": {
        "type": "noul",
        "instructions": "Is `transcription` a real interruption of MOTHER speaking?",
        "criteria": {
            "true": "Order to stop, wait, change, or answer now.",
            "false": "Mere backchannel such as “mm-hm”, noise, or speech that does not interrupt.",
        },
    },
    "phrase_finished": {
        "type": "noul",
        "instructions": "Does the sentence in `transcription` look finished?",
        "criteria": {
            "true": "Complete idea or request.",
            "false": "Cut start, hesitation, or an obvious continuation still coming.",
        },
    },
    "transcription_uncertain": {
        "type": "noul",
        "instructions": (
            "Is the `transcription` doubtful, given optional ASR cues in `context`?"
        ),
        "criteria": {
            "true": "Incoherent or truncated words, or low ASR confidence given.",
            "false": "Intelligible transcription, no doubt cue.",
        },
    },
    "expected_response_length": {
        "type": "choice",
        "instructions": "How long a reply does the person expect for `transcription`?",
        "criteria": {
            "one_word": "Very short: one word, a yes, or a no.",
            "few_sentences": "Short reply, a few sentences.",
            "developed": "An explanation or developed help is explicitly asked.",
        },
    },
    "tone": {
        "type": "choice",
        "instructions": "Which reply tone best fits `transcription`?",
        "criteria": {
            "calm": "Even, neutral, reassuring.",
            "cheerful": "Light, warm, or celebrating.",
            "serious": "Factual and grave.",
            "empathic": "Warm in the face of feeling or difficulty.",
        },
    },
    "frustration": {
        "type": "score",
        "instructions": "How much frustration does the person show in `transcription`?",
        "criteria": [
            "No frustration: calm or neutral tone.",
            "Slight frustration or impatience.",
            "Clear frustration.",
            "Strong frustration, anger, or exasperation.",
        ],
    },
    "needs_current_information": {
        "type": "noul",
        "instructions": "Does `transcription` ask for information that must be up to date?",
        "criteria": {
            "true": "News, price, weather, timetable, availability, or other changing fact.",
            "false": "No time-sensitive information asked.",
        },
    },
    "refers_to_context": {
        "type": "noul",
        "instructions": "Does `transcription` refer to conversation context in `context`?",
        "criteria": {
            "true": "Uses e.g. “that”, “like before”, “you remember”.",
            "false": "Standalone request, or no context given.",
        },
    },
    "requests_memory": {
        "type": "noul",
        "instructions": "Does the person explicitly ask to remember or store something?",
        "criteria": {
            "true": "Explicit ask to remember, note, or keep for later.",
            "false": "No memorisation request.",
        },
    },
    "sensitive_local_action": {
        "type": "noul",
        "instructions": "Does `transcription` ask for a sensitive local action?",
        "criteria": {
            "true": "Action that could change, delete, send, buy, share, or affect the device.",
            "false": "No sensitive local action asked.",
        },
    },
    "contains_personal_data": {
        "type": "noul",
        "instructions": "Does `transcription` contain identifying personal data?",
        "criteria": {
            "true": "Full name, contact, id, address, number, or other sensitive personal data.",
            "false": "No identifying personal data visible.",
        },
    },
    "named_harness": {
        "type": "choice",
        "instructions": (
            "Which harness does the person name explicitly in `transcription`? "
            "Never infer a name; choose none if none is explicit."
        ),
        "criteria": {
            "none": "No harness is explicitly named by the user.",
            "claude": "The user explicitly names Claude.",
            "codex": "The user explicitly names Codex.",
        },
    },
}


def langue() -> str:
    brut = (os.getenv("HA_LANG") or os.getenv("HYPER_AMBIENT_LANG") or "fr").strip().lower()
    brut = brut.replace("_", "-")
    if brut.startswith("en"):
        return "en"
    return "fr"


def t(key: str, **kwargs: Any) -> str:
    table = _TABLES.get(langue(), _FR)
    valeur = table.get(key)
    if valeur is None:
        valeur = _FR.get(key, key)
    if kwargs:
        return valeur.format(**kwargs)
    return valeur


def ui() -> dict[str, str]:
    return {
        "welcome_title": t("ui.welcome_title"),
        "welcome_body": t("ui.welcome_body"),
        "ptt_title": t("ui.ptt_title"),
        "ptt_body": t("ui.ptt_body"),
        "hide_title": t("ui.hide_title"),
        "hide_body": t("ui.hide_body"),
        "a11y": t("ui.a11y"),
        "step": t("ui.step"),
        "skip": t("ui.skip"),
        "continue": t("ui.continue"),
        "no_recording": t("ui.no_recording"),
        "shortcut_in_app": t("ui.shortcut_in_app"),
        "try_hold": t("ui.try_hold"),
        "hearing": t("ui.hearing"),
        "speak": t("ui.speak"),
        "speaking": t("ui.speaking"),
        "hide_config": t("ui.hide_config"),
        "understood": t("ui.understood"),
        "reply": t("ui.reply"),
        "shortcut": t("ui.shortcut"),
        "shortcut_ctrl": t("ui.shortcut_ctrl"),
        "local_model": t("ui.local_model"),
        "remote_call": t("ui.remote_call"),
        "remote_status": t("ui.remote_status"),
        "start": t("ui.start"),
        "start_and_hide": t("ui.start_and_hide"),
        "shortcut_kept": t("ui.shortcut_kept"),
        "channel_not_ready": t("ui.channel_not_ready"),
    }


def system_prompt() -> str:
    from src.brain.local_prompt import LOCAL_SYSTEM_PROMPT, LOCAL_SYSTEM_PROMPT_EN

    return LOCAL_SYSTEM_PROMPT_EN if langue() == "en" else LOCAL_SYSTEM_PROMPT


def questions_jev(code: str | None = None) -> dict[str, dict[str, Any]]:
    from src.ears.jev_reflexe import QUESTIONS

    choisi = (code or langue()).lower()
    if choisi.startswith("en"):
        return QUESTIONS_EN
    return QUESTIONS
