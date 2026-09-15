---
date: 2026-09-14
type: analyse-seance
auteur: Codex interim
statut: livre — correctifs courts poses, activation live non forcee
deadline: soutenance 2026-09-25
---

# Analyse de séance — conséquences et corrections

## Verdict

La séance a ajouté deux capacités utiles, le gain de sortie et la recherche
web, mais elle a aussi montré que la voie de démonstration n'est pas isolée de
la voie d'expérimentation. La panne de son n'était pas un défaut de Pocket TTS :
des essais TTS lourds et le host-agent ont partagé le même conteneur plafonné à
8 Gio, le cgroup a atteint sa limite et le service live a disparu. Tant que ces
deux usages cohabitent, une campagne de qualité vocale peut casser la démo.

L'état produit à annoncer sans ambiguïté est donc :

- `web_search` est disponible à la voix via SearXNG local ; Tavily n'est qu'un
  repli non armé ;
- `ask_codex`, `ask_claude` et `ask_muse` ne sont pas disponibles dans le
  registre vocal live ; `.env.local` ne configure actuellement que
  `SEARXNG_URL` parmi ces outils ;
- MiniCPM5-2B est l'unique cerveau local retenu, sous l'alias `mother-local` ;
- la voix de référence reste Pocket TTS `estelle` + profil `aurora`, avec un
  post-gain nominal de +9 dB à valider dans Presence à l'oreille ;
- la sélection voix v2 n'est pas terminée : 4 MP3 valides sur 10 sont présents
  sur disque ; NeuTTS est gated et les travaux IndexTTS/FireRed ne valent pas
  livraison tant qu'un MP3 validé n'existe pas ;
- les images sont optionnelles et distantes. Le jeton `sk-sp-…` refusé en 401
  n'est pas une preuve de panne WAN 2.7 : ce n'est pas un jeton DashScope
  Model Studio utilisable. Aucun temps de soutenance ne doit dépendre de lui.

## Priorités jusqu'à la soutenance

### P0 — protéger la démo live

1. Interdire tout burn TTS dans le conteneur qui exécute le host-agent. Un
   verrou est maintenant placé dans les deux points d'entrée de la campagne
   voix v2. Il refuse avant chargement de modèle s'il voit
   `serve_hostagent.py`. Il ne tue aucun processus.
2. Ne pas lancer la campagne et la recette vocale simultanément, même avec la
   dérogation. GPU, disque et RAM restent des ressources partagées au-delà du
   seul plafond cgroup.
3. Avant une recette ou une démo : campagne arrêtée/terminée, mémoire revenue,
   cerveau local vivant, host-agent vivant, puis un tour PTT réel. Un port TCP
   publié ne suffit pas : exiger la poignée de main WebSocket, EARS, BRAIN,
   premier audio MOUTH et fin de tour dans le journal.
4. Ne pas modifier la voix de référence pendant la campagne. Les nouveaux TTS
   restent des candidats offline tant qu'ils ne sont pas complets et écoutés.

Le verrou ajouté ne stoppe pas les jobs déjà lancés avant ce patch. Aucune
campagne en cours n'a été interrompue et aucun service n'a été relancé dans
cette mission.

### P1 — rendre les capacités déclarées vérifiables

1. La relance ciblée lit et exporte désormais, sans sourcer `.env.local`, les
   réglages SearXNG/Tavily et les URL/jetons Codex/Claude/Muse. Les valeurs des
   secrets ne sont jamais affichées ; le log ne donne que `oui/non`.
2. `.env.example` documente les URL de pont et précise que les outils restent
   absents si leur réglage requis est vide. Les jetons de pont sont des secrets
   partagés avec les processus `native/*bridge`, pas des clés OpenAI ou
   Anthropic.
3. Au chargement, le host-agent compare désormais les outils attendus d'après
   l'environnement aux schémas réellement inscrits. Une divergence fait
   échouer tôt le démarrage au lieu de produire une démo où MOTHER prétend
   disposer d'un outil absent. `ask_hermes` reste explicitement interdit.
4. Après provisionnement des ponts, vérifier leur endpoint depuis le conteneur
   avant de les promettre à la voix. Avoir un jeton et un schéma ne prouve pas
   qu'un processus hôte écoute.

### P1 — valider l'expérience audible

1. Tester +9 dB dans Presence sur la sortie physique de soutenance. Le sample
   mesuré passe de -21,11 à -13,55 dBFS RMS avec crête à -0,23 dBFS, mais cette
   mesure ne tranche ni la compression perçue ni le niveau du périphérique.
2. Si le limiteur s'entend, revenir à +6 dB. Ne monter à +12 dB qu'après écoute
   sur le matériel final.
3. Faire la recette PTT, raccourci clavier, masquage de la fenêtre de
   configuration et navigation clavier/lecteur d'écran. L'accessibilité est une
   contrainte de sortie, pas une amélioration ultérieure.

### P2 — travaux après sécurisation de la démo

1. Créer un service/conteneur `tts-burn` dédié, sans port 8001 et avec son
   propre plafond mémoire. C'est un changement Compose à planifier ; aucun
   recreate n'a été fait ce soir. Conserver malgré tout l'exclusion mutuelle
   opérationnelle pendant les répétitions.
2. Ajouter une commande unique de prévol qui vérifie mémoire, processus live,
   santé du cerveau local, WebSocket et noms du registre avant la démo.
3. Reprendre NeuTTS seulement après acceptation de la licence HF. Reprendre
   WAN 2.7 seulement avec une vraie clé DashScope et le bon endpoint régional.
4. Prévoir un routing de continuité quand Claude atteint sa limite de session :
   la disponibilité d'un agent de développement ne doit pas être une dépendance
   runtime ni une condition de recette produit.

## Erreurs corrigées ou requalifiées

| Sujet | Mauvaise lecture | Correction / conséquence |
|---|---|---|
| Silence | panne Pocket ou sortie Windows | transport live absent après OOM ; protéger le service |
| MiniCPM | duo MiniCPM5 + MiniCPM 2B | un seul modèle : MiniCPM5-2B |
| Accès agents | ponts supposés disponibles | modules présents, outils live absents faute de config |
| Web | « accès externe complet » | SearXNG oui ; Tavily et agents non |
| WAN 2.7 | modèle cassé | authentification DashScope invalide/non provisionnée |
| Voix v2 | campagne presque livrée | 4/10 MP3 seulement ; jobs/imports ne sont pas des livrables |
| Muse | peut analyser le dépôt | second avis high-level ; son workspace ne voit pas ce projet |
| Gain +9 dB | correction terminée | code et mesure OK, validation oreille encore obligatoire |

## Décisions à figer

- La voie live gagne toujours sur les expériences : aucun TTS burn pendant une
  recette, une répétition ou une démo.
- MiniCPM5-2B est le cerveau local unique. Aucun vocabulaire de « duo ».
- La capacité externe démontrable aujourd'hui est `web_search`. Un agent n'est
  annoncé que lorsque pont, secret, santé réseau et inscription au registre ont
  tous été prouvés.
- Images optionnelles, jamais sur le chemin critique du 25 septembre.
- Onboarding : le modèle local guide ; la fenêtre app configure puis se masque ;
  la fenêtre world reste ; PTT et raccourci sont prévus ; accessibilité requise.
- Voix live figée sur `estelle`/`aurora` pendant la comparaison v2. Le +9 dB est
  provisoirement retenu, sous réserve du test oreille Presence.
- Aucun résultat de campagne n'est compté sans fichier audio valide et écoute.

## Correctifs déposés

- `.env.example` : variables des ponts et du web documentées ;
- `dev/scripts/relancer_routeur.sh` : lecture sûre et export des réglages outils,
  diagnostic booléen sans fuite de secret ;
- `dev/scripts/serve_hostagent.py` : invariant config ↔ registre au démarrage ;
- `dev/scripts/tts_burn_guard.py` : verrou anti-colocation non destructif ;
- `_voix_10_v2_driver.py` et `_voix_10_samples_v2.py` : verrou appelé avant les
  opérations lourdes (`--index` reste autorisé) ;
- tests ajoutés pour le verrou et l'invariant du registre.

La dérogation `TTS_BURN_ALLOW_COLOCATED=1` existe uniquement pour rendre un
choix dangereux explicite et traçable. Elle ne doit pas être utilisée avant la
soutenance.

## Vérification et limites

- `git diff --check` : aucune erreur d'espace ; seulement les avertissements de
  conversion LF/CRLF déjà associés au worktree Windows ;
- `bash -n dev/scripts/relancer_routeur.sh` via Git Bash : OK ;
- état disque confirmé : 4 MP3 (`VoxCPM2`, `Audio8`, `Anka`, `Chatterbox MTL`) ;
- tests Python non exécutables depuis ce shell : aucun Python n'est au PATH, et
  l'accès au moteur Docker/WSL est refusé à cette session. Les tests ont été
  écrits mais restent à lancer dans `mother-core-dev` ;
- aucune relance, aucun recreate, aucun arrêt de job, aucun push, aucun commit.

## Ordre de reprise

1. Laisser finir ou arrêter proprement les jobs TTS déjà en cours ; ne pas les
   relancer dans le conteneur live.
2. Lancer dans le conteneur existant :
   `python -m pytest dev/tests/test_tts_burn_guard.py dev/tests/test_outils_voix.py -q`.
3. Ajouter les secrets/URL de pont voulus dans `.env.local`, démarrer les ponts
   hôte correspondants, puis seulement relancer le host-agent avec le script
   ciblé. Sans secrets, conserver l'état actuel `web_search` seul.
4. Contrôler la ligne `OUTILS:` puis faire un tour PTT avec recherche web. Si un
   pont est armé, faire un appel court à chacun et vérifier la phrase d'attente.
5. Valider +9 dB à l'oreille dans Presence sur la sortie de soutenance.
6. Une fois le live stable, créer le service Compose TTS dédié et reprendre les
   six samples manquants hors de la voie de démonstration.

