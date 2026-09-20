# Données qui sortent de la machine

Périmètre vérifié dans le code : `src/brain/`, `src/ears/`, `src/mouth/`,
`src/hostagent/`, `native/` et `dev/scripts/serve_hostagent.py`.

## Points à corriger avant publication

- Une transcription et l'historique textuel récent sont envoyés au modèle
  distant lorsqu'il est activé. Ils ne restent donc pas toujours sur la
  machine.
- JeV reçoit la transcription lorsqu'il est activé.
- La recherche peut appeler DuckDuckGo sans clé, après un échec de SearXNG.
- Un pont Muse optionnel existe en plus de Codex et Claude. Un pont Qwen Code
  existe aussi dans `native/`, mais n'est pas branché au host-agent actuel.
- Le lien de retour ouvre GitHub dans le navigateur, sur action explicite.

| Donnée envoyée | Destination | Condition | Désactivation |
|---|---|---|---|
| Transcription, instruction système, historique récent et éventuels résultats d'outils ; clé d'API dans l'en-tête si elle est configurée | Endpoint de modèle configuré par l'utilisateur | Service `stepfun`, `openai`/compatible, ou routeur avec voie distante. Le mode de repli peut appeler le distant avant de revenir au local. | Utiliser `BRAIN_SERVICE=llamacpp` et une URL locale ; ne pas configurer d'endpoint distant ni de clé. |
| Transcription ; clé d'API dans l'en-tête | API JeV (`api.typesafe.ai`) | Mains libres actif et clé JeV présente. Des requêtes de préchauffage sans transcription peuvent aussi maintenir la connexion. | Retirer la clé JeV ou désactiver le mains libres. |
| Requête de recherche ; clé du fournisseur dans l'en-tête lorsque nécessaire | SearXNG configuré, puis DuckDuckGo, Tavily, Brave, Exa, Jina ou Serper | L'outil de recherche est enregistré si une URL SearXNG ou au moins une clé de recherche est configurée. DuckDuckGo est le repli sans clé. | Retirer `SEARXNG_URL` et toutes les clés de recherche : l'outil n'est alors pas enregistré. |
| Question vocale transformée en texte | Pont local Codex ou Claude, puis les services des CLIs installées et connectées par l'utilisateur | Jeton de pont configuré, puis choix de l'outil par le modèle. | Retirer le jeton du pont concerné ou ne pas lancer son pont. |
| Question vocale transformée en texte | URL du pont Muse configurée | `MUSE_BRIDGE_URL` est défini et le modèle choisit `ask_muse`. | Retirer `MUSE_BRIDGE_URL`. |
| Question vocale transformée en texte | Qwen Code, via le pont Qwen | Le pont `native/qwenbridge` est lancé séparément et reçoit une requête. Le host-agent actuel ne l'enregistre pas comme outil. | Ne pas lancer ce pont. |
| Ouverture de la page de création d'issue | GitHub, via le navigateur système | Clic explicite sur le lien de retour. Le code ne joint aucun contenu à l'URL. | Ne pas utiliser ce lien. |

## Ce qui reste local dans ce périmètre

- Le code inspecté n'envoie pas l'audio brut à un service distant. Presence et
  le host-agent échangent les trames audio sur le canal local `127.0.0.1` ; le
  serveur refuse les pairs non-loopback.
- Il n'y a pas d'appel de télémétrie, de création de compte ou de serveur du
  projet dans ce périmètre.
- Les réglages et clés viennent de l'environnement et de fichiers locaux. Ils
  ne sont pas transmis au projet ; une clé est toutefois présentée au service
  choisi quand une requête authentifiée est faite.
- `RemoteTTS` contient un client d'API distant, mais le host-agent actuel ne
  l'instancie dans aucun choix `MOUTH_BACKEND`. Magpie utilise `127.0.0.1`.

Cette description porte sur les appels explicites du code inspecté. Les CLIs
et les bibliothèques de modèles installées par l'utilisateur ont leurs propres
comportements réseau, hors de ce code.
