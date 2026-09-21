# Données qui sortent de la machine

Périmètre vérifié dans le code : `src/brain/`, `src/ears/`, `src/mouth/`,
`src/hostagent/`, `native/` et `dev/scripts/serve_hostagent.py`.

| Donnée envoyée | Destination | Condition | Désactivation |
|---|---|---|---|
| Transcription, instruction système, historique récent et éventuels résultats d'outils ; clé d'API dans l'en-tête si elle est configurée | Endpoint de modèle distant configuré par l'utilisateur | Tous les tours difficiles, et tout tour qui nomme un harnais (Codex ou Claude Code), passent par le distant afin qu'il raisonne et pilote les outils. | Utiliser un service local et ne pas configurer d'endpoint distant ni de clé ; les harnais ne sont alors pas pilotables par cette voie. |
| Transcription ; clé d'API dans l'en-tête | API JeV (`api.typesafe.ai`) | Mains libres actif et clé JeV présente. Des requêtes de préchauffage sans transcription peuvent aussi maintenir la connexion. | Retirer la clé JeV ou désactiver le mains libres. |
| Requête de recherche ; clé du fournisseur dans l'en-tête lorsque nécessaire | SearXNG configuré, puis DuckDuckGo, Tavily, Brave, Exa, Jina ou Serper | L'outil de recherche est enregistré si une URL SearXNG ou au moins une clé de recherche est configurée. DuckDuckGo est le repli sans clé. | Retirer `SEARXNG_URL` et toutes les clés de recherche : l'outil n'est alors pas enregistré. |
| Question transmise par un pont Codex ou Claude local | Service de la CLI Codex ou Claude installée et connectée par l'utilisateur | Le pont appelle une CLI connectée ; le comportement réseau de ce service dépend alors du compte et de la configuration de cette CLI. | Déconnecter la CLI ou ne pas lancer le pont. |
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
- Les ponts Codex, Claude, Muse et Qwen sont locaux. Leur échange avec
  hyper-ambient ne fait pas sortir de donnée de la machine. Un service distant
  éventuellement appelé ensuite par une CLI connectée est décrit dans le tableau.
- Les transcriptions de conversation sont écrites progressivement, une
  conversation par fichier Markdown, dans
  `data/conversations/YYYY-MM-DD_HH-mm.md` à la racine de l'installation. Le
  conteneur y écrit `/workspace/data/conversations/`. Elles restent sur la
  machine et ne déclenchent aucun envoi réseau. Elles contiennent l'heure, la
  personne qui parle, le texte et les lignes d'appels d'outil ou de mandat afin
  de pouvoir être relues dans un éditeur de texte. Le chemin
  `%LOCALAPPDATA%\hyper-ambient\conversations\` ne s'applique qu'à une
  exécution hors conteneur.
- `RemoteTTS` contient un client d'API distant, mais le host-agent actuel ne
  l'instancie dans aucun choix `MOUTH_BACKEND`. Magpie utilise `127.0.0.1`.

Cette description porte sur les appels explicites du code inspecté. Les CLIs
et les bibliothèques de modèles installées par l'utilisateur ont leurs propres
comportements réseau, hors de ce code.

## Prochaine évolution vérifiée à prévoir

Un produit installé devra écrire les transcriptions dans
`%LOCALAPPDATA%\hyper-ambient\conversations\`. Avec l'architecture conteneur
actuelle, cela demandera un volume supplémentaire vers cet emplacement ; il
n'est pas encore présent.
