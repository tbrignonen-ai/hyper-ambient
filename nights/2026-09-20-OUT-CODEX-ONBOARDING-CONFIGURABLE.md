---
date: 2026-09-20
type: out
scope: onboarding configurable + instance Presence isolee
method: lecture des decisions, du code Presence et des noms de variables seulement
---

# Ce qui est configurable dans l'onboarding hyper-ambient

## Réponse courte

L'onboarding réellement livré est un **wizard graphique classique, en quatre écrans** : Bienvenue, Mains libres, PTT, Masquage. Il n'est pas assisté par le modèle local : il ne charge pas le modèle, ne prononce pas le guide et ne fait aucune conversation de configuration. Le modèle local intervient seulement après la sortie du wizard, via le host-agent, pour une conversation PTT normale.

La cible Muse — onboarding oral, guidé par le modèle local, skippable — est une proposition UX. La cible LLM V1 (Déclarer, Guider, Armer, Essayer) est spécifiée mais n'est pas implémentée. Les configurations de modèle, harnais, JeV, recherche et voix restent donc aujourd'hui des paramètres de déploiement, pas des champs du wizard.

## Tableau des réglages

| Élément | Décision / source | État réel | Si absent ou non configuré |
|---|---|---|---|
| Langue | Muse ; audit du 20. | **Implémenté**, formulaire classique sur Bienvenue ; `presence.json` contient `langue`. `HA_LANG` ou `HYPER_AMBIENT_LANG` déjà présents priment. | Sans préférence ni variable, français. |
| Contraste | Design Codex, § Accessibilité ; audit du 20. | **Implémenté**, case classique sur Bienvenue ; `presence.json` contient `contraste`. | `False` : palette normale. |
| Raccourci PTT | Design Codex, § PTT et raccourci ; Cursor, § Onboarding. | **Implémenté**, radios Espace / Ctrl+Espace dans le wizard, persistés dans `presence.json`. Il ne fonctionne que lorsque la fenêtre a le focus. | `Espace` ; JSON invalide ou valeur inconnue revient aussi à Espace et relance le wizard si nécessaire. |
| Mains libres / JeV | `2026-09-20-ONBOARDING-OUT.md` et `2026-09-20-OUT-PRESENCE-JEV-MAINS-LIBRES.md`. | **Implémenté**, écran classique Activer / Plus tard, bouton ultérieur et `mains_libres` dans `presence.json`; l'option WS est envoyée au host-agent. Ce n'est pas un micro ouvert ni du VAD continu. | `False` : PTT au maintien, JeV non demandé. |
| Masquage de la configuration | Design Codex, § Configuration qui se masque ; Cursor, § Onboarding. | **Implémenté** : `iconify()` ; action explicite « Commencer et masquer ». | La fenêtre reste visible avec le bouton Masquer ; pas de tray ni de hotkey global. |
| Modèle local | Muse, étapes 1–2 ; LLM V1, § 2–3 ; carte figée. | **Spécifié pour l'accueil assisté**, mais **non implémenté dans l'onboarding**. Le host-agent utilise la carte de déploiement : `BRAIN_SERVICE`, `BRAIN_MODEL`, `BRAIN_MODEL_LOCAL`, `MODEL`, `LLAMA_SERVER_HOST`. | Aucun écran ne l'installe, ne le charge ni ne le diagnostique. Après le wizard, l'app tente le canal audio/host-agent et affiche une erreur textuelle s'il est indisponible. |
| Modèle distant d'escalade | Cursor, § Éclair ; LLM V1, étape Déclarer ; audit du 20. | **Indicateur implémenté** seulement : éclair + texte durant l'état `escalade`. Le formulaire nom/URL/clé, test `/health` et persistance séparée sont **spécifiés, non implémentés**. Paramètres de déploiement observés : `BRAIN_API_KEY`, `BRAIN_API_ENDPOINT`, `BRAIN_MODEL`, `BRAIN_TIMEOUT_MS`, `BRAIN_TTFT_DEADLINE_MS`. | Pas de distant déclaré ni vérifié ; aucun appel n'est « connecté » par le wizard. Le routage reste celui du host-agent. |
| Harnais Codex | LLM V1, étapes Armer / Essayer. | **Spécifié, non implémenté dans l'onboarding**. Le pont lit `CODEX_BRIDGE_TOKEN` et, si besoin, `CODEX_BRIDGE_URL`. | Pont fermé ou outil indisponible ; pas de pastilles Up/token/PONG et pas de fallback d'onboarding. |
| Harnais Claude | LLM V1, étapes Armer / Essayer. | **Spécifié, non implémenté dans l'onboarding**. Le pont lit `CLI_BRIDGE_TOKEN` et, si besoin, `CLI_BRIDGE_URL`. | Pont fermé ou outil indisponible ; pas de pastilles Up/token/PONG et pas de fallback d'onboarding. |
| JeV — clé/service | LLM V1 prévoit seulement un health de gateway connu ; note JeV du 20. | **Partiellement implémenté** : l'activation Mains libres envoie l'option JeV, mais aucun écran ne demande ni ne vérifie une clé/service JeV. La configuration de déploiement observée comprend `TYPESAFE_API_KEY`. | Mains libres peut rester activable côté UI, mais il n'y a aucune preuve ni diagnostic d'un service JeV manquant. |
| Recherche web | LLM V1, checklist Guider ; aucun écran dédié dans les décisions PTT. | **Pas configurable dans l'onboarding**. Les paramètres observés sont `SEARXNG_URL` et `TAVILY_API_KEY`. | L'outil concerné n'est pas armé par le wizard ; l'absence est traitée par le composant de recherche, hors UI Presence. |
| Micro et haut-parleur | Muse, étape Voix ; Design Codex, § Accessibilité ; audit du 20. | **Partiellement implémenté** : le wizard ne sollicite pas le micro. L'app accepte `--device` et `--sortie`, mais ne propose pas de sélecteur dans l'onboarding. Paramètres moteur : `EARS_BACKEND`, `EARS_MODEL`, `EARS_LANGUAGE`, `EARS_DEVICE`, `EARS_COMPUTE_TYPE`, `EARS_HOTWORDS`. | Sélection par défaut PortAudio ; périphérique/dépendance absent après le wizard → erreur texte non bloquante. Aucune aide de correction ni parcours d'essai utile n'existe encore. |
| Voix de réponse | Muse, étapes 2–4 ; Design Codex, § Accessibilité ; carte figée. | **Pas de choix dans l'onboarding**. Le moteur est configurable au déploiement par `MOUTH_BACKEND`, `MOUTH_STYLE`, `MOUTH_SPEED`, `MOUTH_VOICE_NAME`, `MOUTH_LANGUAGE`, `MOUTH_DEVICE`, `MOUTH_PROFILE`, `MOUTH_OUTPUT_GAIN_DB`, `MOUTH_VOICE`. | La configuration de déploiement / les défauts du moteur s'appliquent ; le wizard ne propose ni voix ni lecture seule. |
| Vidéo / présence visuelle | Muse, étape 5 ; Design Codex, § Vidéo optionnelle. | **Spécifiée mais hors tranche**, donc non implémentée et non persistée. | Voix seule, sans option UI pour démarrer l'overlay. |

`dev/scripts/carte_figee.env` porte les noms de déploiement du modèle local, de l'oreille et de la voix ci-dessus. `.env.local` contient notamment les noms des variables de distant, web et harnais ci-dessus, ainsi que `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `DASHSCOPE_API_KEY`, `DASHSCOPE_REGION`, `STEPFUN_API_KEY`, `STEPFUN_BASE_URL`, `HF_TOKEN`, `HF_HOME`, `HF_HUB_OFFLINE`, `ALIAS`, `CTX` et `TURN_SILENCE_MS`. Aucune valeur de clé n'est reproduite ici.

Important : le chargeur du host-agent ne propage depuis `.env.local` que les clés d'outils/langue autorisées ; la carte figée reste la source des paramètres modèle/oreille/voix. Ce n'est donc pas un second système de réglages que le wizard pourrait déjà éditer.

## Formulaire classique ou assistance par modèle local

| Partie | Réalité actuelle |
|---|---|
| Wizard PTT | Formulaire Tk classique : radios, case à cocher, boutons. Il est terminable sans micro ni serveur. |
| Conversation après « Commencer » | Assistée par le modèle local seulement si le host-agent, le modèle, l'audio et le WebSocket sont disponibles. Ce n'est pas de la configuration. |
| Onboarding conversationnel oral | Seulement spécifié par Muse ; absent. |
| Déclarer / Guider / Armer / Essayer LLM V1 | Seulement spécifié ; absent. |

## Seconde instance vierge, isolée

Le code accepte déjà un profil avec `--config`. J'ai ajouté `--journal` et fait analyser les arguments avant l'initialisation de stdout/stderr : sous `pythonw`, chaque instance peut désormais écrire dans son propre journal au lieu du journal par défaut partagé. Il n'existe pas de verrou de processus Presence dans le code actuel : il n'y a donc aucun fichier de verrou à séparer.

Commande PowerShell, copiable depuis n'importe quel répertoire. Elle crée un répertoire neuf à chaque lancement, force l'onboarding, isole configuration, journal et fichier santé, et pointe le futur canal vocal vers le port distinct 8002 :

```powershell
Set-Location "D:\BGB Training\MOTHER-dev"
$state = Join-Path $env:LOCALAPPDATA ("hyper-ambient\presence-onboarding-" + [guid]::NewGuid().ToString())
New-Item -ItemType Directory -Path $state | Out-Null
$arguments = "native/presence/app.py --onboarding --config `"$(Join-Path $state 'presence.json')`" --journal `"$(Join-Path $state 'presence.log')`" --sante `"$(Join-Path $state 'health.json')`" --url ws://127.0.0.1:8002/hostagent"
Start-Process -FilePath "C:\Users\thoma\AppData\Local\Programs\Python\Python313\pythonw.exe" -WorkingDirectory "D:\BGB Training\MOTHER-dev" -ArgumentList $arguments
```

Avant « Commencer », cette seconde fenêtre ne démarre ni micro ni WebSocket : elle est donc appropriée pour tester le wizard sans perturber l'instance en cours. Ses fichiers sont tous sous le nouveau `$state` : `presence.json`, `presence.log` et le chemin santé isolé.

## Conflits restants — signalés explicitement

- Le port 8002 est volontairement distinct, mais aucun second host-agent n'est lancé par Presence. Après « Commencer », cette instance affichera donc une erreur de connexion sur 8002. C'est une isolation sûre pour tester l'onboarding, pas une seconde assistante fonctionnelle.
- Si elle est redirigée vers le port 8001 de l'agent hôte existant, les deux instances partageront ce WebSocket et pourront se disputer le micro et la sortie audio : ne pas le faire pendant les tests de la première instance.
- Pour rendre deux conversations réellement indépendantes, il faut aussi lancer un second host-agent avec ses propres port, environnement et ressources audio ; ce lancement n'est ni fourni ni configuré par `native/presence/app.py`.
- Les deux fenêtres gardent le même AppUserModelID Windows et la même icône : elles peuvent être groupées dans la barre des tâches, sans partage de données.

## Vérification

- `native/presence/app.py` : option `--journal`, employée avant l'UI.
- Test ajouté : le parseur accepte le journal d'instance.
- `python -m py_compile native/presence/app.py native/presence/onboarding.py` : OK.
- `python -m pytest dev/tests/test_taquet_produit.py -q` (hôte Windows) : 8 passés.
- Référence : `docker exec mother-core-dev python -m pytest dev/tests -q --ignore=dev/tests/test_health_sondes.py` : 1323 passés, 5 échecs pré-existants, 25 ignorés, 2 xfailed ; aucun échec nouveau.
- Aucun secret lu ou affiché ; les variables sont nommées uniquement.
