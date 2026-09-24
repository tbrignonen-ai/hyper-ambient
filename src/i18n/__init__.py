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
        "Quatre réglages suffisent : mains libres, comment parler, quel raccourci, comment masquer."
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
    "ui.stop": "Stop",
    "ui.interrupted": "Interrompue.",
    "ui.interrupted_listening": "Interrompue — je t'écoute.",
    "ui.listening_toggle": "Écoute…",
    "ui.tap_to_send": "Appuie pour envoyer",
    "ui.listening_tap_send": "Écoute… Réappuie pour envoyer.",
    "ui.sending": "Envoi…",
    "ui.hide_config": "Masquer la configuration",
    "ui.settings": "Réglages",
    "ui.understood": "Compris",
    "ui.reply": "Réponse",
    "ui.shortcut": "Espace",
    "ui.shortcut_ctrl": "Ctrl + Espace",
    "ui.local_model": "Cerveau distant",
    "ui.remote_call": "Appel distant…",
    "ui.harness_front": "Harnais au premier plan",
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
    "ui.hands_free_connecting": "Connexion…",
    "ui.hands_free_connected": "Mains libres prêtes.",
    "ui.channel_ready": "Canal prêt. Maintenez Parler ou {raccourci}.",
    "ui.channel_ready_hands_free": (
        "Canal prêt. Appuyez sur Parler ou {raccourci} — réappuyez pour envoyer."
    ),
    "ui.connecting": "Connexion…",
    "ui.listening": "Écoute… relâchez pour envoyer.",
    "ui.no_frames": "Aucune trame capturée (parole trop courte).",
    "ui.frames_sent": "{n} trames envoyées, attente de la réponse…",
    "ui.first_sound": "premier son : {ms:.0f} ms",
    "ui.replying": "Réponse en cours.",
    "ui.feedback": "Feedback",
    "ui.feedback_url": "https://github.com/tbrignonen-ai/hyper-ambient/issues/new",
    "ui.contrast": "Contraste élevé",
    "ui.language": "Langue",
    "ui.hands_free": (
        "Mains libres : un appui sur Parler démarre l'écoute, un second envoie. "
        "Pas besoin de maintenir. Ce n'est pas un micro ouvert en continu. "
        "Avec une clé JeV, Hyper Ambient n'intervient que si on s'adresse à elle. "
        "Sans clé, le bouton Parler reste le repli. "
        "Ce n'est pas un mode pour personnes sourdes : l'oreille et la voix "
        "restent le canal, avec tout le texte à l'écran (malvoyants, clavier, focus)."
    ),
    "ui.hands_free_title": "Mains libres",
    "ui.hands_free_on": "Mains libres : ON — appuyez Parler",
    "ui.hands_free_off": "Mains libres : OFF",
    "ui.hands_free_enable": "Activer",
    "ui.hands_free_later": "Plus tard",
    "ui.hands_free_hint": (
        "Pas un micro ouvert. Appuyez Parler ou {raccourci} pour écouter, "
        "réappuyez pour envoyer ; JeV n'ignore que les apartés."
    ),
    "ui.conversation_open": "En conversation — {n} s",
    "ui.conversation_invite": "Dis mon nom pour me parler",
    "mandat.accuse": "Je demande à {harnais} de {sujet}. Je te préviens.",
    "mandat.rappel": "{harnais} prend du temps, je te préviens dès que c'est prêt.",
    "mandat.fini": "{harnais} a fini.",
    "mandat.offre": "Tu veux le détail, ou que je te l'ouvre ?",
    "mandat.renvoi_outil": "Le détail est dans {harnais}, je te l'ai ouvert.",
    "session.reprise": (
        "Je reprends la session {harnais} « {titre} ». "
        "Tes prochaines demandes à {harnais} iront dedans."
    ),
    "session.reprise_sans_titre": (
        "Je reprends la dernière session {harnais}. "
        "Tes prochaines demandes à {harnais} iront dedans."
    ),
    "session.introuvable": "Je n'ai trouvé aucune session {harnais} qui parle de {sujet}.",
    "session.introuvable_partout": "Je n'ai trouvé aucune session qui parle de {sujet}.",
    "session.aucune": "Je n'ai trouvé aucune session {harnais}.",
    "session.nouvelle": "D'accord, ta prochaine demande à {harnais} ouvrira une nouvelle session.",
    "session.absent": "{harnais} n'est pas branché, je ne peux pas rejoindre ses sessions.",
    "session.aucun_pont": "Aucun harnais n'est branché, je ne peux rejoindre aucune session.",
    "session.et": " et à ",
    "mandat.echoue": "{harnais} n'a pas répondu. J'arrête d'attendre.",
    "mandat.plein": "J'ai déjà trois mandats en cours. Je ne peux pas en prendre un de plus.",
    "mandat.sans_resume": (
        "{harnais} a répondu mais je n'ai pas de résumé. "
        "Tu veux le détail, ou que je te l'ouvre ?"
    ),
    "mandat.badge": "{n} résultat prêt",
    "reglages.titre": "Réglages",
    "reglages.enregistrer": "Enregistrer",
    "reglages.tout_verifier": "Tout vérifier",
    "reglages.verifier": "Vérifier",
    "reglages.je_verifie": "Je vérifie…",
    "reglages.enregistre": "Réglages enregistrés.",
    "reglages.echec_sonde": "La vérification n'a pas abouti.",
    "reglages.brain_titre": "Modèle distant",
    "reglages.brain_aide": (
        "Un modèle distant est fortement recommandé. "
        "C'est lui qui prend les demandes difficiles. "
        "Il est recommandé de choisir un modèle dont on peut désactiver "
        "le raisonnement. Un modèle qui réfléchit longuement avant de "
        "répondre est pénible à l'oral : on attend dans le silence. "
        "On peut aussi passer par l'abonnement déjà connecté de Codex "
        "ou de Claude Code, sans aucune clé API."
    ),
    "reglages.outil_codex_titre": "Harnais Codex",
    "reglages.outil_codex_aide": (
        "Le programme Codex déjà installé sur cette machine. "
        "C'est ton abonnement ChatGPT Plus, pas une clé."
    ),
    "reglages.outil_claude_titre": "Harnais Claude Code",
    "reglages.outil_claude_aide": (
        "Le programme Claude Code déjà installé sur cette machine. "
        "C'est ton abonnement Claude Pro, pas une clé."
    ),
    "reglages.codex_titre": "Pont Codex",
    "reglages.codex_aide": (
        "Elle peut lui confier du travail dans l'outil de code déjà installé."
    ),
    "reglages.claude_titre": "Pont Claude Code",
    "reglages.claude_aide": (
        "Elle peut lui confier une analyse dans Claude Code déjà installé."
    ),
    "reglages.jev_titre": "JeV (TypeSafe AI)",
    "reglages.jev_aide": (
        "C'est ce qui lui permet de savoir quand on s'adresse à elle, "
        "et donc ce qui rend les mains libres possibles."
    ),
    "reglages.champ.BRAIN_API_ENDPOINT": "Adresse du modèle",
    "reglages.champ.BRAIN_MODEL": "Nom du modèle (BRAIN_MODEL)",
    "reglages.champ.BRAIN_MODEL_exemple": (
        "Exemple : gpt-4.1, claude-sonnet-4 — le nom exact attendu par le fournisseur."
    ),
    "reglages.champ.BRAIN_API_KEY": "Clé du modèle",
    "reglages.champ.CODEX_BRIDGE_URL": "Adresse du pont Codex",
    "reglages.champ.CODEX_BRIDGE_TOKEN": "Jeton Codex",
    "reglages.champ.CLI_BRIDGE_URL": "Adresse du pont Claude",
    "reglages.champ.CLI_BRIDGE_TOKEN": "Jeton Claude",
    "reglages.champ.TYPESAFE_MODEL": "Nom du modèle (TYPESAFE_MODEL)",
    "reglages.champ.TYPESAFE_MODEL_exemple": (
        "Exemple : jev-latest — le nom exact attendu par TypeSafe AI."
    ),
    "reglages.champ.TYPESAFE_API_KEY": "Clé JeV",
    "reglages.posee": "déjà posée : {suffixe}",
    "reglages.a11y": (
        "Tab parcourt les champs. Entrée active un bouton. "
        "Échap ferme les réglages sans quitter l'application."
    ),
    "reglages.confidentialite": (
        "Hyper Ambient ne collecte aucune donnée. "
        "Tout ce qui sort va vers les services que vous avez choisis."
    ),
    "reglages.categorie.machine": "Sur votre machine",
    "reglages.categorie.outils": "Vos outils, vos abonnements",
    "reglages.categorie.distants": "Services distants",
    "reglages.donnees.modele_local": (
        "Données locales. Rien ne quitte cette machine."
    ),
    "reglages.donnees.outil_codex": (
        "Données locales. Communique avec le pont local Codex, "
        "qui utilise votre propre abonnement."
    ),
    "reglages.donnees.outil_claude": (
        "Données locales. Communique avec le pont local Claude Code, "
        "qui utilise votre propre abonnement."
    ),
    "reglages.donnees.codex": (
        "Données locales. Communique avec le pont local Codex, "
        "qui utilise votre propre abonnement."
    ),
    "reglages.donnees.claude": (
        "Données locales. Communique avec le pont local Claude Code, "
        "qui utilise votre propre abonnement."
    ),
    "reglages.donnees.brain_distant": (
        "Données envoyées au modèle distant que vous avez choisi."
    ),
    "reglages.donnees.jev": "Données envoyées à TypeSafe AI. Optionnel.",
    "reglages.donnees.recherche": (
        "Données envoyées au moteur dont vous avez posé la clé."
    ),
    "reglages.donnees.cles": "Données locales. Fichier sur cette machine.",
    "reglages.donnees.voix": (
        "Données locales. Rien ne quitte cette machine."
    ),
    "reglages.donnees.langue": (
        "Données locales. Rien ne quitte cette machine."
    ),
    "reglages.verifier_aide": (
        "Vérifier appelle réellement le service, avec un délai de cinq secondes."
    ),
    "reglages.echec_manuel": (
        "Si un test échoue, les réglages restent modifiables à la main "
        "dans le fichier .env.local."
    ),
    "reglages.detecter_abonnements": "Détecter mes abonnements",
    "reglages.modele_local_titre": "Modèle local",
    "reglages.modele_local_aide": (
        "Le modèle qui tourne ici. Rien de ce bloc ne quitte cette machine."
    ),
    "reglages.voix_titre": "Voix",
    "reglages.voix_aide": (
        "Choisissez à l'oreille. La synthèse vocale reste sur cette machine. "
        "Le changement prend effet au prochain redémarrage du moteur vocal."
    ),
    "reglages.voix_repli": "Liste de repli : le serveur vocal ne répond pas.",
    "reglages.accent_titre": "Accent",
    "reglages.accent_aucun": "Aucun accent",
    "reglages.accent_compromis": (
        "Un accent rend la voix plus charmante, un peu moins facile à comprendre."
    ),
    "reglages.accent.en": "Accent anglais",
    "reglages.accent.es": "Accent espagnol",
    "reglages.accent.de": "Accent allemand",
    "reglages.accent.fr": "Accent français",
    "reglages.accent.it": "Accent italien",
    "reglages.accent.vi": "Accent vietnamien",
    "reglages.accent.hi": "Accent hindi",
    "reglages.accent.autre": "Accent ({code})",
    "reglages.voix_ecouter": "Écouter",
    "reglages.voix_extrait": "Bonjour, je suis là.",
    "reglages.voix_ecouter_echec": (
        "Le serveur vocal ne répond pas. L'extrait n'a pas pu être joué."
    ),
    "reglages.renvoi_outil": "Renvoyer vers l'outil pour le détail",
    "reglages.langue_titre": "Langue",
    "reglages.langue_aide": (
        "La langue de l'interface. On ne la change qu'une fois."
    ),
    "reglages.langue_delai": (
        "Ce réglage ne change que l'interface. "
        "La reconnaissance et la synthèse gardent leurs propres réglages ; "
        "un rechargement des modèles peut être nécessaire."
    ),
    "reglages.langue_en_cours": "Changement de langue…",
    "reglages.cerveau_titre": "Cerveau distant",
    "reglages.cerveau_aide": (
        "Qui converse quand la question dépasse le modèle local : une clé "
        "d'API, ou votre abonnement Claude ou ChatGPT, par le harnais déjà "
        "connecté. La liste des modèles vient du harnais."
    ),
    "reglages.donnees.cerveau_distant": (
        "Données envoyées au service choisi : votre clé d'API, ou votre "
        "abonnement Claude ou ChatGPT."
    ),
    "reglages.cerveau_mode": "Qui converse",
    "reglages.cerveau_mode.api": "Clé d'API (MiniMax ou compatible)",
    "reglages.cerveau_mode.abonnement-claude": "Abonnement Claude (Claude Code)",
    "reglages.cerveau_mode.abonnement-chatgpt": "Abonnement ChatGPT (Codex)",
    "reglages.cerveau_modele": "Modèle",
    "reglages.cerveau_appliquer": "Appliquer",
    "reglages.cerveau_api": "La clé d'API se règle dans le bloc suivant.",
    "reglages.cerveau_liste": "Lecture des modèles disponibles…",
    "reglages.cerveau_en_cours": "Application… la voix redémarre (une minute).",
    "reglages.cerveau_applique": "Appliqué. La voix utilise ce modèle.",
    "reglages.cerveau_echec": "Échec de la relance. Vérifiez que Docker tourne.",
    "reglages.langue.fr": "Français",
    "reglages.langue.en": "Anglais",
    "reglages.recherche_titre": "Recherche web",
    "reglages.recherche_aide": (
        "Optionnel. Si vous avez posé une clé, la requête part vers ce moteur."
    ),
    "reglages.recherche_tavily": (
        "Tavily est recommandé pour démarrer : gratuit au début, sans carte bancaire. "
        "Sans aucune clé, la recherche est possible mais peu fiable. "
        "Créer un compte : https://app.tavily.com"
    ),
    "reglages.cles_titre": "Clés et réglages",
    "reglages.cles_aide": (
        "Elles restent dans votre fichier local, sur cette machine."
    ),
    "reglages.menu": "Aide",
    "reglages.invite.BRAIN_API_ENDPOINT": "ex. https://api.exemple/v1",
    "reglages.invite.BRAIN_MODEL": "ex. gpt-4.1",
    "reglages.invite.BRAIN_API_KEY": "coller une nouvelle clé",
    "reglages.invite.CODEX_BRIDGE_URL": "ex. http://127.0.0.1:8765/ask",
    "reglages.invite.CODEX_BRIDGE_TOKEN": "coller un nouveau jeton",
    "reglages.invite.CLI_BRIDGE_URL": "ex. http://127.0.0.1:8766/ask",
    "reglages.invite.CLI_BRIDGE_TOKEN": "coller un nouveau jeton",
    "reglages.invite.TYPESAFE_MODEL": "ex. jev-latest",
    "reglages.invite.TYPESAFE_API_KEY": "coller une nouvelle clé",
    "sondes.outil_absent": (
        "L'outil {nom} n'est pas installé. Dans PowerShell : {commande}"
    ),
    "sondes.outil_present": (
        "L'outil {nom} est installé. "
        "La connexion de l'abonnement n'a pas été vérifiée. "
        "Pour vous connecter, dans PowerShell : {commande}"
    ),
    "sondes.outil_inconnu": "Cet outil n'est pas un harnais connu.",
    "sondes.outil_echec": "L'outil {nom} n'a pas pu être vérifié.",
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
        "Four settings: hands-free, how to talk, which shortcut, how to hide."
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
    "ui.stop": "Stop",
    "ui.interrupted": "Interrupted.",
    "ui.interrupted_listening": "Interrupted — listening.",
    "ui.listening_toggle": "Listening…",
    "ui.tap_to_send": "Press to send",
    "ui.listening_tap_send": "Listening… Press again to send.",
    "ui.sending": "Sending…",
    "ui.hide_config": "Hide settings",
    "ui.settings": "Settings",
    "ui.understood": "Heard",
    "ui.reply": "Reply",
    "ui.shortcut": "Space",
    "ui.shortcut_ctrl": "Ctrl + Space",
    "ui.local_model": "Remote brain",
    "ui.remote_call": "Remote call…",
    "ui.harness_front": "Bring harness to front",
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
    "ui.hands_free_connecting": "Connecting…",
    "ui.hands_free_connected": "Hands-free ready.",
    "ui.channel_ready": "Channel ready. Hold Talk or {raccourci}.",
    "ui.channel_ready_hands_free": (
        "Channel ready. Press Talk or {raccourci} — press again to send."
    ),
    "ui.connecting": "Connecting…",
    "ui.listening": "Listening… release to send.",
    "ui.no_frames": "No frames captured (speech too short).",
    "ui.frames_sent": "{n} frames sent, waiting for a reply…",
    "ui.first_sound": "first sound: {ms:.0f} ms",
    "ui.replying": "Reply in progress.",
    "ui.feedback": "Feedback",
    "ui.feedback_url": "https://github.com/tbrignonen-ai/hyper-ambient/issues/new",
    "ui.contrast": "High contrast",
    "ui.language": "Language",
    "ui.hands_free": (
        "Hands-free: press Talk to start listening, press again to send. "
        "No need to hold. This is not a continuously open mic. "
        "With a JeV key, Hyper Ambient only answers when addressed. "
        "Without a key, the Talk button is the fallback. "
        "This is not a mode for deaf users: hearing and speech stay the channel, "
        "with all text on screen (low vision, keyboard, focus)."
    ),
    "ui.hands_free_title": "Hands-free",
    "ui.hands_free_on": "Hands-free: ON — tap Talk",
    "ui.hands_free_off": "Hands-free: OFF",
    "ui.hands_free_enable": "Enable",
    "ui.hands_free_later": "Later",
    "ui.hands_free_hint": (
        "Not an open mic. Press Talk or {raccourci} to listen, "
        "press again to send; JeV only ignores side talk."
    ),
    "ui.conversation_open": "In conversation — {n} s",
    "ui.conversation_invite": "Say my name to talk to me",
    "mandat.accuse": "I'll ask {harnais} to {sujet}. I'll let you know.",
    "mandat.rappel": "{harnais} is taking a while — I'll let you know as soon as it's ready.",
    "mandat.fini": "{harnais} is done.",
    "mandat.offre": "Want the detail, or shall I open it?",
    "mandat.renvoi_outil": "The detail is in {harnais}, I've opened it for you.",
    "session.reprise": (
        "I'm back in the {harnais} session “{titre}”. "
        "Your next requests to {harnais} will go there."
    ),
    "session.reprise_sans_titre": (
        "I'm back in the latest {harnais} session. "
        "Your next requests to {harnais} will go there."
    ),
    "session.introuvable": "I found no {harnais} session about {sujet}.",
    "session.introuvable_partout": "I found no session about {sujet}.",
    "session.aucune": "I found no {harnais} session.",
    "session.nouvelle": "Okay, your next request to {harnais} will start a new session.",
    "session.absent": "{harnais} isn't connected, I can't join its sessions.",
    "session.aucun_pont": "No harness is connected, I can't join any session.",
    "session.et": " and ",
    "mandat.echoue": "{harnais} didn't answer. I'll stop waiting.",
    "mandat.plein": "I already have three mandates in progress. I can't take another.",
    "mandat.sans_resume": (
        "{harnais} answered but I don't have a summary. "
        "Want the detail, or shall I open it?"
    ),
    "mandat.badge": "{n} result ready",
    "reglages.titre": "Settings",
    "reglages.enregistrer": "Save",
    "reglages.tout_verifier": "Check all",
    "reglages.verifier": "Check",
    "reglages.je_verifie": "Checking…",
    "reglages.enregistre": "Settings saved.",
    "reglages.echec_sonde": "The check did not complete.",
    "reglages.brain_titre": "Remote model",
    "reglages.brain_aide": (
        "A remote model is strongly recommended. "
        "It is the one that takes the hard requests. "
        "Pick a model whose reasoning can be turned off. "
        "A model that thinks at length before answering is painful "
        "spoken aloud: you wait in silence. "
        "You can also go through the already-connected Codex or "
        "Claude Code subscription, with no API key."
    ),
    "reglages.outil_codex_titre": "Codex harness",
    "reglages.outil_codex_aide": (
        "The Codex program already installed on this machine. "
        "That is your ChatGPT Plus subscription, not a key."
    ),
    "reglages.outil_claude_titre": "Claude Code harness",
    "reglages.outil_claude_aide": (
        "The Claude Code program already installed on this machine. "
        "That is your Claude Pro subscription, not a key."
    ),
    "reglages.codex_titre": "Codex bridge",
    "reglages.codex_aide": (
        "She can hand work to the coding tool already installed."
    ),
    "reglages.claude_titre": "Claude Code bridge",
    "reglages.claude_aide": (
        "She can hand an analysis to Claude Code already installed."
    ),
    "reglages.jev_titre": "JeV — TypeSafe AI",
    "reglages.jev_aide": (
        "This is how she knows she is being addressed, "
        "and what makes hands-free possible."
    ),
    "reglages.champ.BRAIN_API_ENDPOINT": "Model address",
    "reglages.champ.BRAIN_MODEL": "Model name (BRAIN_MODEL)",
    "reglages.champ.BRAIN_MODEL_exemple": (
        "Example: gpt-4.1, claude-sonnet-4 — the exact name the provider expects."
    ),
    "reglages.champ.BRAIN_API_KEY": "Model key",
    "reglages.champ.CODEX_BRIDGE_URL": "Codex bridge address",
    "reglages.champ.CODEX_BRIDGE_TOKEN": "Codex token",
    "reglages.champ.CLI_BRIDGE_URL": "Claude bridge address",
    "reglages.champ.CLI_BRIDGE_TOKEN": "Claude token",
    "reglages.champ.TYPESAFE_MODEL": "Model name (TYPESAFE_MODEL)",
    "reglages.champ.TYPESAFE_MODEL_exemple": (
        "Example: jev-latest — the exact name TypeSafe AI expects."
    ),
    "reglages.champ.TYPESAFE_API_KEY": "JeV key",
    "reglages.posee": "already set: {suffixe}",
    "reglages.a11y": (
        "Tab moves through the fields. Enter activates a button. "
        "Escape closes settings without quitting the app."
    ),
    "reglages.confidentialite": (
        "Hyper Ambient collects no data. "
        "Anything that leaves goes to the services you chose."
    ),
    "reglages.categorie.machine": "On your machine",
    "reglages.categorie.outils": "Your tools, your subscriptions",
    "reglages.categorie.distants": "Remote services",
    "reglages.donnees.modele_local": (
        "Data stays local. Nothing leaves this machine."
    ),
    "reglages.donnees.outil_codex": (
        "Data stays local. Talks to the local Codex bridge, "
        "which uses your own subscription."
    ),
    "reglages.donnees.outil_claude": (
        "Data stays local. Talks to the local Claude Code bridge, "
        "which uses your own subscription."
    ),
    "reglages.donnees.codex": (
        "Data stays local. Talks to the local Codex bridge, "
        "which uses your own subscription."
    ),
    "reglages.donnees.claude": (
        "Data stays local. Talks to the local Claude Code bridge, "
        "which uses your own subscription."
    ),
    "reglages.donnees.brain_distant": (
        "Data is sent to the remote model you chose."
    ),
    "reglages.donnees.jev": "Data is sent to TypeSafe AI. Optional.",
    "reglages.donnees.recherche": (
        "Data is sent to the search engine whose key you set."
    ),
    "reglages.donnees.cles": "Data stays local. File on this machine.",
    "reglages.donnees.voix": (
        "Data stays local. Nothing leaves this machine."
    ),
    "reglages.donnees.langue": (
        "Data stays local. Nothing leaves this machine."
    ),
    "reglages.verifier_aide": (
        "Check actually calls the service, with a five-second timeout."
    ),
    "reglages.echec_manuel": (
        "If a check fails, settings can still be edited by hand "
        "in the .env.local file."
    ),
    "reglages.detecter_abonnements": "Detect my subscriptions",
    "reglages.modele_local_titre": "Local model",
    "reglages.modele_local_aide": (
        "The model that runs here. Nothing in this block leaves this machine."
    ),
    "reglages.voix_titre": "Voice",
    "reglages.voix_aide": (
        "Choose by ear. Speech synthesis stays on this machine. "
        "The change takes effect the next time the voice engine restarts."
    ),
    "reglages.voix_repli": "Fallback list: the voice server is not answering.",
    "reglages.accent_titre": "Voice accent",
    "reglages.accent_aucun": "No accent",
    "reglages.accent_compromis": (
        "An accent makes the voice more charming, and a little harder to understand."
    ),
    "reglages.accent.en": "English accent",
    "reglages.accent.es": "Spanish accent",
    "reglages.accent.de": "German accent",
    "reglages.accent.fr": "French accent",
    "reglages.accent.it": "Italian accent",
    "reglages.accent.vi": "Vietnamese accent",
    "reglages.accent.hi": "Hindi accent",
    "reglages.accent.autre": "{code} accent",
    "reglages.voix_ecouter": "Listen",
    "reglages.voix_extrait": "Hello, I am here.",
    "reglages.voix_ecouter_echec": (
        "The voice server is not answering. The sample could not be played."
    ),
    "reglages.renvoi_outil": "Point to the tool for the detail",
    "reglages.langue_titre": "Language",
    "reglages.langue_aide": (
        "The interface language. You only change it once."
    ),
    "reglages.langue_delai": (
        "This setting only changes the interface. "
        "Recognition and speech keep their own settings; "
        "the models may need to reload."
    ),
    "reglages.langue_en_cours": "Changing language…",
    "reglages.cerveau_titre": "Remote brain",
    "reglages.cerveau_aide": (
        "Who converses when a question goes beyond the local model: an API "
        "key, or your Claude or ChatGPT subscription through the harness you "
        "already connected. The model list comes from the harness."
    ),
    "reglages.donnees.cerveau_distant": (
        "Data sent to the chosen service: your API key, or your Claude or "
        "ChatGPT subscription."
    ),
    "reglages.cerveau_mode": "Who converses",
    "reglages.cerveau_mode.api": "API key (MiniMax or compatible)",
    "reglages.cerveau_mode.abonnement-claude": "Claude subscription (Claude Code)",
    "reglages.cerveau_mode.abonnement-chatgpt": "ChatGPT subscription (Codex)",
    "reglages.cerveau_modele": "Model",
    "reglages.cerveau_appliquer": "Apply",
    "reglages.cerveau_api": "The API key is set in the next block.",
    "reglages.cerveau_liste": "Reading available models…",
    "reglages.cerveau_en_cours": "Applying… the voice restarts (one minute).",
    "reglages.cerveau_applique": "Applied. The voice uses this model.",
    "reglages.cerveau_echec": "Restart failed. Check that Docker is running.",
    "reglages.langue.fr": "French",
    "reglages.langue.en": "English",
    "reglages.recherche_titre": "Web search",
    "reglages.recherche_aide": (
        "Optional. If you set a key, the query goes to that search engine."
    ),
    "reglages.recherche_tavily": (
        "Tavily is recommended to start: free at first, no credit card. "
        "Without any key, search is possible but unreliable. "
        "Create an account: https://app.tavily.com"
    ),
    "reglages.cles_titre": "Keys and settings",
    "reglages.cles_aide": (
        "They stay in your local file, on this machine."
    ),
    "reglages.menu": "Help",
    "reglages.invite.BRAIN_API_ENDPOINT": "e.g. https://api.example/v1",
    "reglages.invite.BRAIN_MODEL": "e.g. gpt-4.1",
    "reglages.invite.BRAIN_API_KEY": "paste a new key",
    "reglages.invite.CODEX_BRIDGE_URL": "e.g. http://127.0.0.1:8765/ask",
    "reglages.invite.CODEX_BRIDGE_TOKEN": "paste a new token",
    "reglages.invite.CLI_BRIDGE_URL": "e.g. http://127.0.0.1:8766/ask",
    "reglages.invite.CLI_BRIDGE_TOKEN": "paste a new token",
    "reglages.invite.TYPESAFE_MODEL": "e.g. jev-latest",
    "reglages.invite.TYPESAFE_API_KEY": "paste a new key",
    "sondes.outil_absent": (
        "The {nom} tool is not installed. In PowerShell: {commande}"
    ),
    "sondes.outil_present": (
        "The {nom} tool is installed. "
        "The subscription connection was not checked. "
        "To sign in, in PowerShell: {commande}"
    ),
    "sondes.outil_inconnu": "This tool is not a known harness.",
    "sondes.outil_echec": "The {nom} tool could not be checked.",
}

_ES: dict[str, str] = {
    "ui.conversation_open": "En conversación — {n} s",
    "ui.conversation_invite": "Di mi nombre para hablarme",
}

_TABLES = {"fr": _FR, "en": _EN}

QUESTIONS_EN: dict[str, dict[str, Any]] = {
    "assistant_name_spoken": {
        "type": "noul",
        "instructions": (
            "Is the Hyper Ambient assistant's name spoken or clearly "
            "transcribed in `transcription`?"
        ),
        "criteria": {
            "true": (
                "Count Hyper Ambient and close ASR deformations: "
                "“hyper ambiant”, “hyper ambiance”, “hyper ambient”, "
                "“super ambiante”, “HA”, “MOTHER”. The name alone is enough."
            ),
            "false": (
                "None of these names or variants is spoken. Do not infer a "
                "name from an isolated word such as “ambiance” or “super”."
            ),
        },
    },
    "direct_interpellation": {
        "type": "noul",
        "instructions": (
            "Does the person directly address an interlocutor in "
            "`transcription`?"
        ),
        "criteria": {
            "true": (
                "Greeting or direct call: “hello”, “hi”, “hey”, “he”, "
                "“hi there”, “hello?”, “listen”, “tell me”, or vocative. "
                "Count a greeting alone: without contrary context, it "
                "addresses someone. Also count a formulation directly in "
                "the second person."
            ),
            "false": (
                "No address: narration, descriptive sentence, thinking out "
                "loud, or speech identifiably exchanged between other people."
            ),
        },
    },
    "request_or_command": {
        "type": "noul",
        "instructions": (
            "Does the person make a request, a question or an order to an "
            "interlocutor in `transcription`?"
        ),
        "criteria": {
            "true": (
                "Question expecting an answer (“can you hear me?”, "
                "“can you…?”), request, or imperative (“search”, “stop”, "
                "“wait”, “give me”)."
            ),
            "false": (
                "Mere statement, narration, reading, unfinished sentence, or "
                "a reported question that does not ask the present "
                "interlocutor for an answer."
            ),
        },
    },
    "third_party_conversation": {
        "type": "noul",
        "instructions": (
            "Are the words clearly meant for another person present or a "
            "third party, rather than the assistant?"
        ),
        "criteria": {
            "true": (
                "Identifiable conversation between humans, instruction to a "
                "colleague or relative, or message meant for a third party: "
                "e.g. “I'll send you the document after lunch”, “so we were "
                "saying module two”."
            ),
            "false": (
                "No identifiable third party; a request or greeting could be "
                "for the assistant. The name Hyper Ambient/MOTHER/HA is never "
                "a third party."
            ),
        },
    },
    "read_broadcast_recited": {
        "type": "noul",
        "instructions": (
            "Is `transcription` read, broadcast or recited content, rather "
            "than spontaneous speech addressed to the assistant?"
        ),
        "criteria": {
            "true": (
                "Television, radio, film, advertisement, credits, narration, "
                "reading aloud, dictation, song lyrics or recited text: e.g. "
                "“and now, tonight's film” or “Directed by…”."
            ),
            "false": (
                "Spontaneous speech to an interlocutor, even if it contains a "
                "greeting, a question or an order."
            ),
        },
    },
    "reported_or_quoted_speech": {
        "type": "noul",
        "instructions": (
            "Does `transcription` report, quote or imitate speech instead of "
            "addressing it to the assistant now?"
        ),
        "criteria": {
            "true": (
                "Reported or quoted speech, e.g. “he asked: can you hear me?”, "
                "“she said hello”, or repeating an example."
            ),
            "false": (
                "The person themselves now speaks the greeting, question, "
                "request or order to get an answer."
            ),
        },
    },
    "unaddressed_self_talk": {
        "type": "noul",
        "instructions": (
            "Is the person speaking without addressing any interlocutor?"
        ),
        "criteria": {
            "true": (
                "Thinking out loud, personal comment, monologue or "
                "observation with no call, request or addressee."
            ),
            "false": (
                "They address someone, make a request/question/order, speak "
                "to a third party, or read/broadcast content."
            ),
        },
    },
    "real_interruption": {
        "type": "noul",
        "instructions": (
            "Is `transcription` a real interruption of the assistant speaking?"
        ),
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
    brut = (os.getenv("HA_LANG") or os.getenv("HYPER_AMBIENT_LANG") or "fr").strip().lower()
    if brut.startswith("es") and key in _ES:
        valeur = _ES[key]
    else:
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
        "stop": t("ui.stop"),
        "interrupted": t("ui.interrupted"),
        "interrupted_listening": t("ui.interrupted_listening"),
        "listening_toggle": t("ui.listening_toggle"),
        "tap_to_send": t("ui.tap_to_send"),
        "listening_tap_send": t("ui.listening_tap_send"),
        "sending": t("ui.sending"),
        "hide_config": t("ui.hide_config"),
        "settings": t("ui.settings"),
        "understood": t("ui.understood"),
        "reply": t("ui.reply"),
        "shortcut": t("ui.shortcut"),
        "shortcut_ctrl": t("ui.shortcut_ctrl"),
        "local_model": t("ui.local_model"),
        "remote_call": t("ui.remote_call"),
        "harness_front": t("ui.harness_front"),
        "remote_status": t("ui.remote_status"),
        "start": t("ui.start"),
        "start_and_hide": t("ui.start_and_hide"),
        "shortcut_kept": t("ui.shortcut_kept"),
        "channel_not_ready": t("ui.channel_not_ready"),
        "hands_free_connecting": t("ui.hands_free_connecting"),
        "hands_free_connected": t("ui.hands_free_connected"),
        "channel_ready": t("ui.channel_ready"),
        "channel_ready_hands_free": t("ui.channel_ready_hands_free"),
        "connecting": t("ui.connecting"),
        "listening": t("ui.listening"),
        "no_frames": t("ui.no_frames"),
        "frames_sent": t("ui.frames_sent"),
        "first_sound": t("ui.first_sound"),
        "replying": t("ui.replying"),
        "feedback": t("ui.feedback"),
        "feedback_url": t("ui.feedback_url"),
        "contrast": t("ui.contrast"),
        "language": t("ui.language"),
        "hands_free": t("ui.hands_free"),
        "hands_free_title": t("ui.hands_free_title"),
        "hands_free_on": t("ui.hands_free_on"),
        "hands_free_off": t("ui.hands_free_off"),
        "hands_free_enable": t("ui.hands_free_enable"),
        "hands_free_later": t("ui.hands_free_later"),
        "hands_free_hint": t("ui.hands_free_hint"),
        "conversation_open": t("ui.conversation_open"),
        "conversation_invite": t("ui.conversation_invite"),
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
