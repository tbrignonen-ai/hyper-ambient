# Chasse aux bugs — chemin vocal nominal Windows / français

Date : 2026-09-20  
Périmètre : diagnostic seulement. Aucun fichier de code n'a été modifié et aucune commande Git n'a été exécutée.

## Verdict court

Les deux constats sont expliqués par le chemin réellement lancé, qui n'est **pas** le routeur : la carte figée force `BRAIN_SERVICE=llamacpp` et le journal du conteneur confirme `BRAIN : llama.cpp`. Le modèle est `granite-4.2-3b-Q4_K_M`. `web_search` est bien enregistré ; il n'est simplement pas rendu obligatoire et le petit modèle répond naturellement à la méta-question au lieu d'appeler un outil.

La mémoire parlée est de **6 messages, donc trois échanges complets**. C'est insuffisant pour une conversation orale suivie au-delà de trois questions/réponses. Il y a en plus une fuite sémantique : le dernier résultat d'outil est réinjecté indéfiniment dans chaque tour ultérieur.

## Ce que disent réellement les journaux

- `/tmp/hostagent.log` contient 295 lignes : démarrage de `serve_hostagent`, `OUTILS: ask_claude, ask_codex, calculer, web_search`, puis uniquement des `GET /` à 404. Il ne contient ni `AUDIO_RECV`, ni `TRANSCRIPT`, ni `BRAIN`, ni `OUTIL` pour les tours vus dans le journal Windows.
- `C:\Users\thoma\AppData\Local\hyper-ambient\presence.log` prouve des connexions prêtes, des `AUDIO_SEND`, des fins de tour, et des ruptures WebSocket : `received 1012 (service restart)`, puis `did not receive a valid HTTP response` et `no close frame received or sent`.

Conclusion de preuve : le journal conteneur disponible ne permet pas d'attribuer la phrase « Est-ce que tu arrives à accéder au web ? » à un appel précis ; il a été recréé après les tours ou les traces ne sont pas corrélées. Il établit toutefois la configuration réelle et l'absence de télémétrie de tour exploitable. Les conclusions de code ci-dessous ne supposent pas une trace qui n'existe pas.

## Constats prioritaires

### CASSE LA DEMO — question sur le Web : réponse déclarative sans appel

**Symptôme constaté.** À « Est-ce que tu arrives à accéder au web ? », elle affirme pouvoir chercher en temps réel et décrit la capacité, sans lancer `web_search`.

**Cause racine.** Le chemin actif passe directement au modèle local, pas par `RouterBrain` : [carte_figee.env](../dev/scripts/carte_figee.env) lignes 7--10 force `llamacpp`, et [factory.py](../src/brain/factory.py) lignes 182--188 retourne alors directement `LlamaCppBrain`. L'hypothèse « classé REFLEXE, donc schémas retirés » ne s'applique donc pas à la session réelle.

Le registre est correct : [serve_hostagent.py](../dev/scripts/serve_hostagent.py) lignes 421--436 inscrit `web_search` dès qu'un backend Web est configuré, et le journal confirme sa présence. La boucle transmet les schémas ([tool_loop.py](../src/brain/tool_loop.py) lignes 182--198). En revanche, [openai_compat.py](../src/brain/openai_compat.py) lignes 126--132 n'envoie aucun `tool_choice` quand l'appelant n'en fournit pas : le comportement est donc `auto`.

Le seul contrat de l'outil est « information à jour », « actualité, météo, prix, ou fait postérieur à l'entraînement » ([tools_web.py](../src/brain/tools_web.py) lignes 29--32). La question entendue est une méta-question sur une capacité, pas une demande de fait actuel ; rien dans le prompt système local ([local_prompt.py](../src/brain/local_prompt.py) lignes 8--13) ni dans la description d'outil ne commande de vérifier effectivement l'accès. Au contraire, le prompt qualifie un oui/non de « fait simple » et demande une seule phrase. Une réponse déclarative est donc le résultat attendu du contrat actuel, pas un incident isolé du modèle.

Le modèle Granite 3B est un facteur aggravant plausible pour l'appel d'outil en mode `auto`, mais il n'est pas nécessaire pour expliquer le défaut : l'orchestrateur n'impose ni route sémantique ni appel de vérification.

### VISIBLE — mémoire : trois échanges seulement

**Symptôme utilisateur.** À partir du quatrième échange, elle oublie le début de la conversation ou perd des références (« comme on disait », un choix formulé au début, une contrainte déjà donnée).

**Cause racine.** `MEMOIRE_MESSAGES = 6` ([serve_hostagent.py](../dev/scripts/serve_hostagent.py) ligne 62). Après chaque réponse non vide, deux messages sont ajoutés puis tout sauf les six derniers est supprimé (lignes 1640--1643). La mémoire ne contient donc exactement que trois paires utilisateur/assistante. `_historique_pour_modele` recopie ce buffer tel quel au tour suivant (lignes 965--980), et `_flux_brain` le transmet effectivement au modèle (lignes 1018--1029).

**Suffisance.** Trois échanges suffisent à interpréter « oui, vas-y » juste après une question ; ils ne suffisent pas à une conversation parlée normale, où la quatrième ou cinquième prise de parole réutilise régulièrement le sujet ou les contraintes du début. La valeur actuelle privilégie une micro-interaction, pas une conversation.

**Coût d'une hausse.** Le serveur actif a une fenêtre de contexte de 4 096 tokens (processus `llama-server` : `--ctx-size 4096`). Chaque échange ajouté consomme les tokens du texte prononcé par l'humain plus ceux de la réponse. Ordre de grandeur vocal court : environ 30 à 100 tokens par paire ; passer de 3 à 6 échanges ajoute donc typiquement 90 à 300 tokens à chaque préremplissage, soit environ 2 à 7 % des 4 096 tokens, plus la latence de préfill correspondante. Le coût varie avec la longueur réelle des réponses, pas avec `MEMOIRE_MESSAGES` seul. Il est très inférieur au plafond de contexte dans une conversation courte ; il devient important surtout avec les résultats d'outil de 1 200 caractères, qui ne sont pas comptés dans la constante.

## Autres défauts réels du chemin nominal

### CASSE LA DEMO — une notification de mandat arrive après la fin du tour et décale la socket

**Symptôme utilisateur.** Si un mandat Codex/Claude finit juste après une réponse, son annonce ne se joue pas ; elle est lue comme le début de la réponse à la prochaine question. Ensuite le protocole peut mêler cette annonce, le rapport et la fin de l'autre tour.

**Cause.** Le client considère `{"frames": []}` comme l'unique fin de tour et sort de `consommer_reponse` ([native/presence/app.py](../native/presence/app.py) lignes 216--226 et 306--310). Or le serveur émet ce marqueur à la fin de `_enchainer` ([serve_hostagent.py](../dev/scripts/serve_hostagent.py) ligne 1692), libère le verrou, puis `_tour` appelle `annoncer_mandats_prets` (lignes 1251--1255). Cette méthode synthétise et envoie des trames via `_dire_maintenant` (lignes 1129--1146), sans rapport ni nouveau marqueur de fin. Les trames restent donc sur la socket après la fin que le client a consommée.

### VISIBLE — le dernier résultat d'outil ne s'efface jamais

**Symptôme utilisateur.** Après une recherche ou un appel distant, l'assistante peut continuer à ramener un résultat ancien dans le sujet des tours suivants ; la conversation grossit aussi durablement d'un bloc pouvant atteindre 1 200 caractères.

**Cause.** Chaque outil produit est conservé dans `_dernier_outils` ([serve_hostagent.py](../dev/scripts/serve_hostagent.py) lignes 1531--1541 puis 1644--1645). `_historique_pour_modele` l'ajoute à chaque tour sous le rôle `user` ([serve_hostagent.py](../dev/scripts/serve_hostagent.py) lignes 971--979). Aucun chemin ne le vide après le « tour suivant » annoncé dans son commentaire ; un tour sans outil ne remplace donc jamais ce buffer. Ce n'est ni borné par `MEMOIRE_MESSAGES`, ni présenté au modèle sous le rôle `tool`.

### CASSE LA DEMO — le produit affirme « pas un micro ouvert », le code ouvre une capture continue

**Symptôme utilisateur.** En activant « Mains libres », la promesse affichée est « Ce n'est pas un micro ouvert en continu » ([src/i18n/__init__.py](../src/i18n/__init__.py) lignes 88--94). Pourtant les traces Windows montrent explicitement `ML : boucle continue demarree` et plusieurs `ML : segment ... detecte`.

**Cause.** La branche mains libres appelle `_boucle_tours_continus` ([native/presence/app.py](../native/presence/app.py) lignes 705--713). Celle-ci exécute immédiatement `capture.start()` puis tourne tant que le mode est actif (lignes 791--803), découpant et envoyant chaque segment prêt (lignes 828--832). Il s'agit bien d'un micro ouvert continûment avec segmentation VAD ; la formulation UI est factuellement fausse.

### VISIBLE — une coupure/reprise du serveur détruit le tour en cours sans reprise

**Symptôme observé.** Le journal Windows contient plusieurs `1012 (service restart)`, puis des échecs de connexion. Un énoncé ou une réponse en cours est perdu ; l'utilisateur doit recommencer.

**Cause.** Le client interrompt la lecture au premier échec de `recv` et retourne ([native/presence/app.py](../native/presence/app.py) lignes 260--273). La boucle externe attend deux secondes et recrée un WebSocket ([native/presence/app.py](../native/presence/app.py) lignes 647--693), mais elle ne conserve ni les trames envoyées ni l'identifiant d'un tour pour les rejouer ou les faire reprendre. La cause immédiate du redémarrage est hors du code disponible ; l'absence de reprise est, elle, déterministe dans ce code.

### MINEUR — le journal de santé pollue le journal opérationnel de centaines de 404

**Symptôme.** Le seul journal conteneur disponible est presque entièrement rempli de `GET / HTTP/1.1 404 Not Found`, ce qui masque les événements de démarrage et rend le diagnostic de session difficile.

**Cause.** Le worker de santé sonde explicitement `http://127.0.0.1:8001/` ([workers/night_health_vault_note/handlers.py](../workers/night_health_vault_note/handlers.py) lignes 31--35), alors que le serveur vocal n'expose que le WebSocket `/hostagent` ([src/hostagent/transport.py](../src/hostagent/transport.py) lignes 91--92). Ce n'est pas la cause du défaut Web, mais c'est la cause de la pollution des traces.

## Hypothèses demandées : statut

| Hypothèse | Conclusion |
|---|---|
| Le routeur classe la question REFLEXE et retire les schémas | Écartée pour la session réelle : le routeur n'est pas actif (`llamacpp` direct). Le mécanisme existe dans `router.py` lignes 96--106 et 271--284, mais n'est pas emprunté. |
| Le prompt pousse à parler de soi | Partiellement vraie : il n'ordonne jamais la vérification effective ; la règle « oui/non, une phrase » favorise exactement une réponse déclarative. Il interdit en revanche le blabla sur la nature du modèle. |
| Granite 3B est faible en appel d'outil sur méta-question | Plausible, non prouvable avec les journaux conservés. Ce n'est pas la cause racine suffisante : le contrat `auto` sans directive d'usage permet ce résultat. |

## Priorité de correction proposée (sans implémentation)

1. Définir le contrat métier de « peux-tu accéder au Web ? » : test de disponibilité réel ou réponse de capacité. Si le test est voulu, l'imposer hors choix libre du LLM.
2. Remplacer la troncature brute à trois échanges par une politique de mémoire vocale explicite ; au minimum couvrir six échanges et expirer le résultat d'outil après l'unique tour de suivi.
3. Réparer le protocole des notifications de mandat : les émettre comme un tour autonome complet ou les consommer hors tour côté client.
4. Corriger la promesse Mains libres ou le comportement de capture ; ils ne peuvent pas tous deux rester tels quels.
5. Ajouter une corrélation de tour commune aux journaux Windows et conteneur, et remplacer la sonde HTTP 404 par une sonde adaptée.
