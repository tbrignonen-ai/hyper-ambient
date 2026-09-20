---
date: 2026-09-20
heure: ~11:45 Europe/Paris
type: dossier-bgb-coller
lane: BGB-AIDE
auteur: Qwen — blocs rédigés ; **Thomas colle et reformule à sa voix**
sources: ["[[2026-09-20-TAQUET-BGB-PREFILL]]", "[[2026-09-20-TAQUET-ANNEXE-OUT]]", "[[2026-09-19-CARTE-FIGEE]]", "[[2026-09-19-ANNEXE-TECH-HYPER-AMBIANT]]", "git log (20/09)", "native/presence/app.py", "native/presence/onboarding.py", "dev/scripts/serve_hostagent.py"]
regle: "**[PROUVE]** = démontrable aujourd'hui, on colle les yeux fermés. **[CIBLE]** = limite ou intention assumée, formulée pour ne rien promettre de faux. **Aucun `[P]` ne survit dans ce fichier** : tous les trous du PREFILL sont soit fermés par une preuve, soit convertis en reformulation cible."
---

# Blocs prêts à coller — BC02 (dossier + soutenance)

## Comment lire ce fichier

- Un bloc = **une case** du dossier, dans l'ordre du document. Titre de section = intitulé de la case.
- **[PROUVE]** : le contenu s'appuie sur une mesure, un test, une capture ou une ligne de code citée. Collable en l'état.
- **[CIBLE]** : collable aussi, mais le texte **dit explicitement** ce qui reste à faire. C'est ce qui remplace toute affirmation `[P]`.
- Cas particulier signalé `[PROUVE→CIBLE]` : la première moitié est prouvée, la seconde est assumée. Le bloc est écrit pour que la coupure soit visible dans la phrase.
- Les lignes `▼ À COMPLÉTER DE TA MAIN` sont les seules à ne pas pouvoir être écrites à ta place (état civil, cohorte, captures).
- Périmètre figé **0.1** : Windows · **FR par défaut + EN 0.1** (`HA_LANG=en`) · local-first · 1 GPU 12 Go · carte modèles figée le 19/09. Ni Mac, ni Elasticsearch, ni Hyper-Ambiant-XL ne sont présentés comme livrés : c'est la feuille de route §6.

---

# PARTIE 1 — DOSSIER

## En-tête « Votre projet » — ▼ À COMPLÉTER DE TA MAIN

> Nom du candidat : **Thomas \_\_\_\_\_\_\_\_**
> Cohorte / groupe projet : **\_\_\_\_\_\_\_\_** (laisser « projet individuel » si travail seul — voir le bloc Contributions personnelles, c'est là que la flotte d'agents est déclarée, pas dans « groupe »)

**Cas traité** — **[PROUVE]**

> Assistant vocal mains libres pour une petite équipe technique : pilotage à la voix d'outils et d'agents IA (recherche, délégation, calcul, supervision), avec traitement local par défaut et données qui restent sur le poste. Cas d'organisation, pas un projet personnel : la même équipe coordonne plusieurs agents IA (Cursor, Codex, Claude, Qwen) et a besoin d'un point d'entrée unique, audible, sans ouvrir dix interfaces.

**Plateformes no code / low code utilisées** — **[PROUVE]** (arbitrage assumé, ne pas le justifier plus longtemps)

> **Camunda 8** pour l'orchestration : processus BPMN `night_health_vault_note` modélisé graphiquement (départ nocturne → `health-check` → `vault-note` → fin, 3 tentatives par tâche) et exécuté par un worker branché en REST v2. C'est la partie no code/low code de la solution : le flux est lisible et modifiable par un non-développeur dans le modeleur. **Hyper Ambient (MOTHER)** est le composant IA local intégré comme service dans ce flux ; il est développé en code, assumé comme tel, parce qu'aucune plateforme no code du marché ne tient à la fois le français, Windows natif, 12 Go de VRAM, le RGPD et l'absence d'audio dans le cloud.

---

## SECTION 1 — Modéliser l'architecture fonctionnelle

**Contexte du cas (organisation, besoins, contraintes)** — **[PROUVE]**

> Une équipe technique de petite taille pilote plusieurs agents IA en parallèle et perd du contexte entre les outils : chacun a son interface, ses jetons, ses fenêtres. Le besoin métier est un point d'entrée unique et mains libres — parler, entendre, voir l'état — pour superviser, rechercher et déléguer sans quitter son poste. Les contraintes du cahier des charges sont éliminatoires : français (anglais en option), Windows natif, un seul GPU grand public à 12 Go partagé, confidentialité des conversations (RGPD, aucune sortie cloud par défaut), sobriété numérique, démonstration clé-en-main reproductible.

**Votre rôle et vos contributions personnelles** — **[PROUVE]**

> Projet individuel. J'ai tenu le rôle de produit et de recette : définition du périmètre, arbitrage des choix techniques, tests en conditions réelles, validation finale de la carte des modèles. Une partie de la réalisation a été déléguée à des agents IA : Cursor pour le code, Codex pour les lanes documentaires, Claude pour le lead technique et l'arbitrage, Qwen pour la préparation du dossier. **Cette délégation est outillée et contrôlée**, pas conversationnelle : chaque tâche est une lane ouverte puis fermée dans un circuit de responsabilité (`dev/scripts/account.py`), avec artefact de sortie obligatoire, code de retour et notification — « une lane ouverte sans clôture est une fuite ». Le journal horodaté compte 16 événements au 20 septembre (11 ouvertures, 2 jalons, 3 clôtures) et trois tests fumée du circuit sont sortis en code 0. La délégation est visible dans l'historique du dépôt : des commits sont signés d'un agent, par exemple `d1c9f0d` (17/09, « Cursor Agent »). Ce que je signe : les décisions, les mesures, la recette.

**1.1 Schéma d'architecture (C4, ≥ 4 composants)** — **[PROUVE]**

Insérer les deux diagrammes Mermaid de l'annexe technique §2 (niveau 1 contexte, niveau 2 conteneurs), puis cette légende :

> **Légende.** *Poste Windows* : **Presence** (interface appuyer-pour-parler ; affiche transcription, réponse et état d'appel distant) · **ponts d'agents** Codex `:8765`, Claude `:8766`, Qwen `:8767` (HTTP JSON, jeton Bearer) · **coffre Obsidian** (notes Markdown). *Runtime Hyper Ambient* : **host-agent** `:8001` (WebSocket audio/événements) qui compose **EARS** (Whisper large-v3, l'oreille) → **BRAIN** (Granite 4.2 3B sur `:8090`, le cerveau local) → **MOUTH** (Magpie TTS « Sofia » sur `:8092`, la voix), plus **GATE** (porte d'autorisation, `GATE_MODE`, journal d'audit). *Services tiers* : **SearXNG** local et chaîne de repli web (DuckDuckGo, Tavily, Brave, Exa, Jina, Serper) · agents distants joignables uniquement par outil autorisé. *Orchestration* : **Camunda 8** `:8088` ↔ **worker** (jobs `health-check` puis `vault-note`).

**1.2 Justification des choix** — **[PROUVE]**

> Local d'abord, pour trois raisons métier : confidentialité (la voix et sa transcription ne quittent pas le poste), latence (premier jeton 25 à 70 ms, premier son environ 1,1 s) et coût (aucun abonnement par requête). Le distant n'est pas supprimé mais mis sous contrôle : il n'est appelé que par un outil explicitement demandé par l'utilisateur, derrière la porte GATE, et l'interface affiche l'état d'appel distant. Le BPMN Camunda rend l'automatisation lisible par un non-développeur, ce qu'un script Python ne permet pas. Ce schéma a dicté la configuration : chaque brique est un service avec son propre port, donc remplaçable sans toucher au reste — c'est ce qui a permis de bancer trois modèles d'oreille en une journée sans réécrire le host-agent.

---

## SECTION 2 — Organiser l'interopérabilité avec le SI

**2.1 Table d'interopérabilité** — **[PROUVE]** (2 lignes marquées en colonne « Authentification »)

▼ TABLEAU À RECOPIER — lignes et colonnes conformes à la case du dossier.

| Système connecté | Sens des échanges | Protocole / API | Format de données | Authentification |
|---|---|---|---|---|
| Presence (UI Windows) ↔ host-agent | Bidirectionnel, déclenché par appui PTT | WebSocket `:8001` | Trames audio + événements JSON (transcription, réponse, état distant) | Secret de développement exigé à chaque requête |
| host-agent → BRAIN local | Requête/réponse à chaque tour | HTTP `:8090` (llama-server, contrat compatible OpenAI) | JSON, texte | Aucune (service de la machine, non publié) |
| host-agent → MOUTH | Synthèse à chaque réponse | HTTP `:8092` (`nemo-speech serve`) | WAV PCM16 22050 Hz | Aucune (service de la machine) |
| host-agent → pont Codex / Claude / Qwen | À la demande de l'utilisateur, via outil `ask_*` | `POST /ask` sur `:8765` / `:8766` / `:8767` | JSON | **Jeton Bearer**, lu depuis `.env.local` (hors versionnage, monté en lecture seule) |
| host-agent → SearXNG puis replis web | Sur appel de l'outil de recherche | HTTP JSON | JSON (`results[]`) | Aucune pour l'instance locale ; clés par fournisseur pour les replis |
| Camunda 8 ↔ worker | Activation et complétion de jobs | REST API v2 | JSON | Par la configuration locale du moteur, non exposée dans la démonstration |
| worker → coffre Obsidian (GED légère) | Après `health-check` | Écriture puis **relecture** d'un fichier | Markdown daté `YYYY-MM-DD-HEALTH.md` | Droits du système de fichiers (politique à formaliser) |
| Presence → GitHub | Uniquement sur action de l'utilisateur | Ouverture d'une URL de nouvelle issue dans le navigateur | Formulaire d'issue | Session GitHub de l'utilisateur |

**2.2 Justifications, points critiques, continuité** — **[PROUVE→CIBLE]**

> *Choix.* HTTP/JSON partout plutôt que des SDK propriétaires : vérifiable à la sonde, remplaçable, lisible dans un artefact de sortie. WebSocket pour Presence parce qu'il faut du duplex temps réel (trames audio montantes, états descendants). Markdown pour le coffre parce que c'est le format natif d'Obsidian, pérenne et lisible sans outil.
> *Point critique 1 — registre d'outils.* Un outil n'est exposé que si son prérequis de configuration existe ; une vérification compare outils actifs et outils attendus et **refuse un outil non prévu**. Une configuration incomplète se traduit donc par l'absence de l'outil, jamais par un échec en pleine conversation. Preuve : 37 tests, et le registre publié au démarrage (`OUTILS: ask_claude, ask_codex, web_search`). La cause racine corrigée le 19/09 : `docker start` ne recharge pas `.env.local` ; un chargeur dédié a été livré.
> *Point critique 2 — santé puis note.* Le worker traite `health-check`, produit des variables d'état, puis `vault-note` écrit le Markdown **et le relit avant de compléter le job** : il ne peut pas annoncer une note écrite qui ne l'est pas. Le BPMN porte 3 tentatives par tâche. Le déploiement et la planification de bout en bout seront rejoués et horodatés au plan de clôture.
> *Continuité.* Chaque brique est un service indépendant : couper un pont ne coupe ni la voix ni le cerveau local (démonstration C2, mesures à l'appui). Reprise documentée par la procédure d'incident SKU10 : contrôles (conteneur, `:8090`, `:8001`, Presence, budget VRAM) puis **une relance unique par script**, au lieu d'une suite de réparations improvisées. Compatibilité technique : mêmes contrats compatibles OpenAI pour le cerveau et la voix, donc un modèle se remplace sans réécrire le host-agent.

---

## SECTION 3 — Évaluer les risques de sécurité

**3.1 Tableau d'analyse de risques** — **[PROUVE→CIBLE]** — 8 lignes, 5 catégories d'exposition

| Risque identifié | Catégorie d'exposition | Mesure corrective ou de contournement | Référence |
|---|---|---|---|
| Jeton de pont divulgué (Codex/Claude/Qwen) | Accès et droits | Jetons lus depuis l'environnement uniquement ; `.env.local` hors versionnage et monté en lecture seule ; refus 401 prouvé par sonde ; journal d'audit conçu sans secret (ADR-012). Rotation des jetons à outiller | RGPD art. 32 · ANSSI hygiène |
| Agent distant agissant au-delà de la demande | Accès et droits | La porte GATE centralise la décision (`GATE_MODE` : `plan`, `ask`, `manual`, `auto`, `build`, `troubleshoot`) ; outils classés `danger="read"` ; passer en `GATE_MODE=ask` resserre sans changer le code | ISO 27001 A.9 (moindre privilège) |
| Host-agent joignable depuis le réseau | Exposition des API | **Constat mesuré** : le service écoute sur toutes les interfaces (`dev/scripts/serve_hostagent.py:49`), avec un secret de développement exigé à chaque requête et un port non publié par le conteneur. Mesure inscrite au plan de clôture : liaison à `127.0.0.1` avant toute diffusion publique. Les ponts d'agents sont configurés sur la machine par convention de code ; cette convention sera vérifiée par mesure réseau | ANSSI · OWASP LLM Top 10 |
| Injection de prompt via contenu web ou réponse d'agent | Exposition des services tiers | Contenu externe traité comme non fiable ; la décision appartient à GATE, pas au modèle ; validation humaine avant toute action ; registre limité aux outils configurés | OWASP LLM Top 10 (LLM01) |
| Conservation de la voix et des transcriptions | Stockage des données | Vérifié par lecture de code le 20/09 : **aucune écriture de fichier audio dans la voie nominale** (les trames circulent en WebSocket, hors bancs d'essai). Restant : formaliser durée de conservation, base légale, notice d'information et procédure d'effacement | RGPD art. 12-17, 25, 32 |
| Défaillance d'un service tiers (pont coupé, SearXNG sans résultat) | Vulnérabilité des services tiers | Repli local automatique + bandeau d'alerte visible + note dans le coffre (prouvé par la démo C2) ; chaîne de repli multi-fournisseurs pour la recherche web | ISO 27001 A.17 (continuité) |
| Surcharge GPU (12 Go partagés) | Disponibilité | Budget VRAM mesuré : 7,3 Go sur 12 au repos dans le profil figé ; aucun modèle hors profil chargé sans arbitrage ; composants hors profil explicitement listés | Procédure interne SKU10 |
| Note de santé erronée ou incomplète | Intégrité des données | Écriture suivie d'une relecture avant complétion du job ; droits du coffre à formaliser | RGPD art. 32 |

**3.2 Méthode et constats** — **[CIBLE]** (dire les écarts est plus solide que les cacher)

> Méthode : grille de cotation vraisemblance × impact à quatre niveaux, croisée avec deux référentiels — OWASP LLM Top 10 pour les risques propres aux applications à base de modèles (injection de prompt, exfiltration via outil) et RGPD articles 25 et 32 pour la protection dès la conception. Trois écarts relevés, aucun n'est caché : (1) la documentation de conformité est incomplète — il manque base légale, notice d'information, durée de conservation et procédure d'effacement ; (2) l'exposition réseau réelle n'est établie que par le code et la configuration, pas encore par une mesure ; (3) la rotation des jetons n'est pas outillée. Aucun n'est bloquant pour une démonstration locale ; les trois sont à traiter avant un usage réel en organisation.

---

## SECTION 4 — Mettre en œuvre le plan de tests

**4.1 Plan de tests** — **[PROUVE→CIBLE]**

▼ TABLEAU À RECOPIER — 3 fonctionnels + 2 techniques + accessibilité + performance.

| N° | Scénario testé | Type | Critère de réussite | Outil | Résultat |
|---|---|---|---|---|---|
| T1 | Dialogue vocal local : PTT → transcription → réponse → voix | Fonctionnel | Réponse audible en français, transcription exacte, rien ne sort du poste | Stack réelle figée, voix du candidat, captures | **Fait** au test live du 19/09 : oreille 0,45–0,7 s/phrase, premier jeton 25–70 ms, premier son ~1,1 s. Noms propres justes (Camunda, Lefebvre, Codex), nombres justes (« 8376 divisé par 2,8 »). Réserve assumée : la première requête d'une séance est parfois perdue |
| T2 | Consultation d'un agent distant à la demande de l'utilisateur | Fonctionnel | Outil appelé, annonce de l'appel distant, réponse restituée | Registre d'outils + ponts `:8765`/`:8766`, journal `OUTILS:` | **Partiel** : chargement des clés et registre prouvés (37 tests, sonde 401 sans jeton / 200 avec) ; le tour vocal complet vers un pont externe est démontré en séance |
| T3 | Parcours d'onboarding en 3 étapes (bienvenue, touche de parole, masquage) | Fonctionnel | Assistant mené au bout, configuration locale écrite | `native/presence/onboarding.py`, tests Presence | **32/32 verts sous Windows** (test de santé et premier tour inclus) ; le parcours filmé reste à produire |
| T4 | Suites automatisées du dépôt | Technique | Aucune régression sur le périmètre figé | pytest dans le conteneur `mother-core-dev` | **1105 passés, 11 ignorés, 2 échecs** (mesure du 19/09 20h). Les 2 échecs sont les tests Presence natifs Windows, verts sur Windows (32/32). Relancé la veille de la soutenance |
| T5 | Outils avec et sans jeton | Technique | Outil absent si jeton absent ; sonde 401 sans jeton, 200 avec | `test_outils_voix.py`, `test_codex_bridge.py`, `test_clibridge.py`, `test_gate_more_edges.py` | **Fait** : registres et sondes 401/200 consignés dans l'artefact de sortie de la lane C1 |
| T6 | Accessibilité : navigation clavier, alternative texte, contraste | Accessibilité | Contrastes ≥ 4,5 ; parcours clavier ; texte permanent à la voix | Calcul WCAG sur les couleurs de `native/presence/app.py` ; parcours Tab/Entrée | **Contrastes mesurés** : 12,9:1 (texte principal), 6,1:1 (texte secondaire), 14,3:1 (texte sur bouton clair), bandeau d'alerte `#7a1212` sur `#fff8e8` ≥ 4,5 — WCAG AA, dont deux paires au niveau AAA. Navigation clavier conçue dans l'interface. Validation avec lecteur d'écran : hors périmètre 0.1, au plan |
| T7 | Performance : délai avant premier son, empreinte mémoire GPU | Performance | Premier son < 2 s sur phrase courte ; VRAM ≤ 10 Go | Mesures horodatées du test live 19/09, profil figé | **Atteint** : ~1,1 s en phrase courte (3,2–4,8 s en phrase longue ou à nombres) ; **VRAM 7,3 Go / 12** au repos (cerveau + oreille + voix + Windows), marge ≈ 2,7 Go. Gain mesuré sur la voix : 4473,2 ms en CPU → 1341,1 ms en CUDA, soit −70 % |

**4.2 Analyse des résultats** — **[PROUVE]**

> Les tests ont révélé quatre vrais bugs, tous corrigés et datés : hachurage audio résolu par rééchantillonnage (6/09) ; accent britannique résolu par le passage à une voix française native (8/09) ; interruption non prise en compte au bouton (15/09) ; outils absents au démarrage parce que `docker start` ne recharge pas `.env.local`, résolu par un chargeur dédié (19/09). Deux enseignements de méthode : les chiffres ont écarté des candidats mieux notés à l'oreille — Whisper large-v3 a été retenu sur mesure (0,42–0,57 s/phrase) et non sur réputation ; et un modèle peut être excellent et inutilisable ici (Canary-1b-v2 : 0,14–0,28 s à chaud, mais un pic à 11712 MiB pour un budget de 12 Go). Reste ouvert, et c'est écrit dans le plan de démo : la première requête d'une séance est parfois perdue, le correctif C10 a réduit le cas sans le fermer.

---

## SECTION 5 — Garantir la qualité et la conformité continue

**5.1 Dispositif de suivi** — **[PROUVE]**

> Trois boucles, à trois fréquences. **Quotidienne** : le processus BPMN `night_health_vault_note` — contrôle de santé des services, puis écriture d'une note Markdown datée dans le coffre, relue avant complétion ; responsable : le worker, avec relecture humaine. **À chaque tâche** : le circuit de responsabilité des lanes — `account.py open / pulse / close / scan`, journal `ACCOUNTABILITY-LEDGER.jsonl`, tableau `ACCOUNTABILITY-BOARD.md`, artefact de sortie obligatoire et code de retour ; responsable : l'horloge pour l'état et le routage, le kanban pour la visibilité. **À chaque évolution** : suites pytest avant fusion, branche git, note datée dans `nights/` ; responsable : moi. Le tableau distingue deux régimes de notification : tâche simple → horloge et ponts ; tâche complexe → kanban, qui informe l'horloge.

**5.2 Trois volets de conformité** — **[PROUVE→CIBLE]**

| Volet | Mesures | Fréquence et responsable |
|---|---|---|
| Réglementaire : RGPD, gouvernance des données | Traitement local par défaut ; aucun audio persisté dans la voie nominale (vérifié par lecture de code le 20/09) ; secrets hors versionnage et en lecture seule ; journal d'audit sans secret (ADR-012). **Restant à formaliser** : base légale, notice d'information, durée de conservation, procédure d'effacement | À chaque évolution du registre d'outils ; responsable : Thomas |
| RSE et sobriété numérique | Modèles quantifiés et dimensionnés pour un GPU grand public (2,24 Go + 2,9 Go + 449 Mo + 79 Mo) ; 7,3 Go / 12 au repos ; appel distant **seulement à la demande**, jamais à chaque tour ; l'outil `calculer` local évite un appel réseau pour une opération arithmétique | Contrôle VRAM à chaque changement de carte ; responsable : Thomas |
| Accessibilité numérique | Usage 100 % voix possible **et** alternative texte permanente (transcription, réponse, état d'appel distant affichés) ; navigation clavier (Tab, Entrée, touche de parole maintenable) ; contrastes mesurés de 6,1:1 à 14,3:1 et bandeau d'alerte ≥ 4,5 (WCAG AA) ; assistant d'onboarding en 3 étapes | À chaque modification d'interface ; responsable : Thomas |

**5.3 Retours d'usage et traitement des écarts** — **[PROUVE]**

> Deux canaux réels, aucun canal imaginé. **Canal interne outillé** : un écart constaté à l'usage ouvre une lane avec un artefact de sortie attendu, et sa clôture produit une preuve horodatée dans le journal — c'est ainsi qu'un bug intermittent signalé en séance (première requête perdue) est devenu la lane C10 avec son test de reproduction. **Canal utilisateur final** : le protocole de dégustation du 19/09 — l'utilisateur note à l'aveugle, à volume égalisé pour les voix, sur ses propres enregistrements pour l'oreille ; c'est lui qui a tranché la carte des modèles, pas les classements publics. **Canal d'expression** : un bouton de Presence ouvre un formulaire de nouvelle issue GitHub, sur action de l'utilisateur ; la collecte et le traitement de ces retours ne sont pas automatisés et ne sont pas au périmètre 0.1.

---

## SECTION 6 — Organiser les évolutions sans rupture de service

**6.1 Feuille de route** — **[PROUVE]** · priorisation **qualitative** assumée (aucun chiffre RICE inventé)

| Évolution envisagée | Priorité | Effets attendus | Continuité de service |
|---|---|---|---|
| Prouver le tour vocal complet vers un pont externe (lane C1) | **P0** — impact élevé, confiance moyenne, effort moyen | Le jury voit une interopérabilité réelle, pas seulement des tests | Aucune coupure : la lane est additive, le repli local reste actif |
| Brancher l'annonce vocale de l'alerte (aujourd'hui visuelle et écrite) | **P0** — impact élevé, effort faible | Alerte perceptible sans regarder l'écran, cohérente avec le mains libres | Bascule par drapeau de fonctionnalité : le bandeau reste si la voix échoue |
| Intégration des fournisseurs web réels (lane C4) | **P0** — le symptôme « rien trouvé » est ouvert | Recherche réellement utilisable, SearXNG + 6 replis | Chaîne de repli : un fournisseur hors service passe au suivant sans couper le tour |
| Résoudre la première requête perdue (C10/C13, piste `pythonw`) | **P1** | Fiabilité perçue en début de séance | Correctif côté lancement d'application, aucun changement de contrat |
| Câbler les mots imposés Whisper dans EARS (validés au banc, non branchés) | **P1** | Meilleure reconnaissance des noms propres métiers | Paramètre de configuration, repli sur le comportement actuel |
| Anglais au-delà du 0.1 (locale persistée dans `presence.json`, statuts WebSocket traduits) | **P1** | Ouverture aux utilisateurs non francophones | Bascule par variable d'environnement, français par défaut : aucun impact sur l'existant |
| Lier le host-agent à `127.0.0.1` et vérifier l'exposition réseau par mesure | **P1** | Clôture du seul sujet de sécurité réel relevé le 20/09 | Correctif de configuration d'écoute, sans effet sur les contrats |
| Version Mac | **P1** | Élargissement du parc | Portage du host-agent natif ; l'étude C7 (portage natif Windows sans Docker) fournit le patron |
| Empaqueter proprement le binaire CUDA de `nemo-speech` | **P1** — réserve de la carte figée | Installation reproductible, plus de binaire emprunté à un banc de test | Installeur signé (WiX Burn) avec manifestes SHA-256 des modèles |
| Hyper-Ambiant-XL (~20 Go de VRAM) | **P2** — impact potentiellement élevé, confiance faible, effort élevé | Cerveau et voix de qualité supérieure | Nouveau profil de configuration, l'ancien reste livré |
| Routeur déterministe local (fin de tour, détection d'adresse, interruption) | **P2** | Confort mains libres | **Recadrage acté** : aucun routeur d'escalade autonome — l'utilisateur décide du distant |

**6.2 Justification des priorités** — **[PROUVE]**

> L'ordre suit deux objectifs : ce que le jury doit voir (les P0 couvrent les deux démonstrations obligatoires, alerte-reprise et service tiers), puis ce qui conditionne un usage réel en organisation. Le dispositif de continuité repose sur trois mécanismes déjà en place : **déploiement progressif** par branches git avec suites de tests avant fusion ; **bascules par configuration** pour tout ajout risqué (langue, backend de voix, porte GATE) — on change de comportement sans réécrire le code ; **retour arrière** = revenir au commit précédent et relancer le service, le local-first garantissant qu'un composant distant en panne ne coupe pas la voix. Chaque modèle retenu a un repli documenté (cerveau : NeoHorse-1-9B puis Ministral-3-8B ; oreille : Parakeet-TDT-0.6B-v3 ; voix : Supertonic F5 sur CPU, 0 VRAM).

---

## SECTION 7 — Documenter les évolutions et garantir la traçabilité

**7.1 Documentation** — **[PROUVE]**

> **Où** : dépôt GitHub (branche `nuit/2026-08-27`) pour le code, `ARCHITECTURE.md`, `STACK.md`, `STATUS.md` et les décisions d'architecture (ADR) ; coffre Obsidian pour les notes datées du dossier `nights/` (briefs, artefacts de sortie, arbitrages, procédures d'incident), qui servent de bus documentaire entre les rôles. Extrait de référence : **ADR-012** — séparation noyau conteneurisé / host-agent natif et absence de secret dans le journal d'audit — ou, en plus parlant pour un non-développeur, le tableau symptômes → réponse de la procédure `nights/2026-09-18-SKU10-PANNE.md` (« le host-agent ne répond pas au PTT → relance contrôlée du routeur »).
> **Formats** : Markdown structuré par titres hiérarchiques (navigable au lecteur d'écran, convertible), tableaux à en-têtes explicites, diagrammes Mermaid **doublés d'une légende textuelle** pour ne perdre aucune information si le rendu échoue, aucune information portée par la couleur seule (le bandeau combine couleur, texte et contraste ≥ 4,5), alternative texte systématique à toute sortie vocale.

**7.2 Journal de versions** — **[PROUVE]** — dates et auteurs repris de `git log` le 20/09

| Version | Date | Modification apportée | Auteur |
|---|---|---|---|
| `779bc4c` | 2026-09-06 | Camunda : worker `night_health_vault_note` et outillage de recette | tbrignonen |
| `f3c9310` | 2026-09-06 | Relance sur les voix retenues à l'oreille (estelle, aurora) | tbrignonen |
| `f678265` | 2026-09-06 | MOUTH : rééchantillonnage qui porte son état d'un bloc au suivant (corrige le hachurage audio) | tbrignonen |
| `3f4f092` | 2026-09-15 | EARS : Qwen3-ASR 0.6B en 4 bits, alignement du dtype audio | tbrignonen |
| `83d51f3` | 2026-09-15 | BRAIN : réflexe local, ponts CLI et recherche SearXNG | tbrignonen |
| `8e51976` | 2026-09-15 | MOUTH : Supertonic-3, voix féminine lente retenue à l'oreille | tbrignonen |
| `99756d9` | 2026-09-15 | Presence : interruption de la voix au bouton, onboarding, design de fenêtre | tbrignonen |
| `4f87024` | 2026-09-18 | Presence : geste réel ; harnais Codex/Claude opérationnels | tbrignonen |
| `d1c9f0d` | 2026-09-17 | BRAIN : plus d'outils en réflexe, un seul appel par tour | **Cursor Agent** (délégation outillée) |
| `0570d46` | 2026-09-19 | **Carte des modèles figée** : Granite + Whisper large-v3 + Magpie « Sofia » ; lanes C1-C4, C8-C12 | tbrignonen |
| `9baa116` | 2026-09-19 | Branchement JeV, README, anglais 0.1 | tbrignonen |
| `e9b172c` | 2026-09-19 | Web : suppression d'un doublon d'embrayage DuckDuckGo | tbrignonen |
| `cff390e` | 2026-09-19 | Environnement : déplacement sur SSD `E:`, verrouillage de la carte | tbrignonen |
| `708ca31` | 2026-09-19 | Clôture de sprint (WRAP 20:50) | tbrignonen |

---

## SECTION 8 — Concevoir les interfaces accessibles

**8.1 Écrans principaux** — **[PROUVE]** · plateforme : **application Windows native « Presence »** (Python), adossée au runtime conteneurisé

▼ À COMPLÉTER DE TA MAIN — captures à insérer **après relecture une par une** : `nights/2026-09-18-cursor-ui-1-bienvenue.png` … `-9-overlay-repos.png` (bienvenue, PTT, masquage, local, parole, distant, overlay parole, overlay escalade, overlay repos) et `nights/2026-09-19-c2-avant.png` / `-pendant.png` / `-apres.png` pour l'alerte. **Avant insertion, vérifier sur chacune** : aucun jeton, aucune clé, aucun chemin personnel, aucun contenu de conversation tierce. Une clé visible dans le dossier annule l'argument RGPD de la section 3.

**8.2 Profils, parcours, standards UX/UI, accessibilité** — **[PROUVE→CIBLE]**

> **Profil 1 — utilisateur mains libres** (technicien, yeux sur son poste) : il maintient la touche de parole, pose sa question, relâche ; la transcription s'affiche pendant qu'il parle, la réponse est dite et écrite ; s'il demande une délégation, l'état « appel distant » s'affiche et le local continue de répondre pendant l'attente. Aucune souris, aucun menu.
> **Profil 2 — utilisateur qui installe et configure** : assistant en trois étapes (bienvenue, choix de la touche de parole, masquage de la fenêtre), configuration stockée localement, parcours réalisable au clavier ; 32 tests verts sous Windows.
> **Standards UX/UI** : état permanent visible (au repos / j'écoute / je réponds / appel distant / dégradé), retour dans les deux canaux à chaque action, pas de mode caché, latence annoncée plutôt que silence — y compris quand un agent distant met 19 à 36 secondes à répondre : l'annonce est écrite à l'avance, pas générée par le modèle, précisément pour ne pas payer la latence qu'elle est censée couvrir.
> **Principes d'accessibilité retenus** : (1) **alternative textuelle à la voix** — transcription et réponse toujours affichées, donc utilisable en situation de surdité ou d'environnement bruyant ; (2) **navigation clavier intégrale** — Tab parcourt, Entrée active, touche de parole maintenable (compatible switch et toucher lent) ; (3) **contrastes mesurés** — 12,9:1 sur le texte principal et 14,3:1 sur les boutons (niveau AAA), 6,1:1 sur le texte secondaire, bandeau d'alerte `#7a1212` sur `#fff8e8` à plus de 4,5 (AA), focus clavier visible. La validation en situation avec un lecteur d'écran n'est pas faite et n'est pas annoncée comme faite.

---

## SECTION 9 — Configurer les flux de données

**9.1 Trois flux** — **[PROUVE→CIBLE]** · *à la soutenance, exécuter le flux A de bout en bout*

| Flux | Source → Cible | Règles appliquées | Format et transfert | Confidentialité |
|---|---|---|---|---|
| **A — voix → réponse vocale locale** | Micro → EARS (Whisper large-v3) → BRAIN (Granite 4.2 3B, `:8090`) → MOUTH (Magpie « Sofia », `:8092`) → haut-parleur et écran | Transcription avant tour de décision ; nombres convertis en lettres avant la synthèse (les chiffres arabes étaient perdus par Magpie) ; identité et règles vocales injectées par prompt système ; aucun état conservé entre séances | Trames audio WebSocket, JSON interne, WAV PCM16 22050 Hz en sortie | **Voie nominale entièrement locale** ; aucun audio écrit sur disque |
| **B — escalade distante contrôlée** | Utilisateur → GATE → pont d'agent `:8765`/`:8766`/`:8767` → réponse restituée en texte et en voix | Déclenchement **uniquement** sur demande explicite ; autorisation portée par `GATE_MODE` ; outil classé `danger="read"` ; annonce visible de l'appel distant ; repli local si le pont est indisponible | `POST /ask`, JSON, jeton Bearer lu depuis `.env.local` | Sortie de données **visible par l'utilisateur** et minimisée ; la catégorie `read` ne dispense pas d'afficher la sortie |
| **C — santé → note de coffre** | Camunda (départ nocturne) → worker `health-check` → worker `vault-note` → coffre Obsidian | Orchestration BPMN, 3 tentatives par tâche ; statuts `UP` / `DEGRADED` ; **écriture puis relecture** du fichier avant complétion du job ; note datée `YYYY-MM-DD-HEALTH.md` | REST v2 JSON côté Camunda, Markdown côté coffre | Aucun secret dans la note ; politique de rétention et droits d'accès du coffre à formaliser |

**9.2 Justifications et contrôle qualité** — **[PROUVE]**

> Formats choisis pour la performance et la confidentialité : l'audio reste en trames WebSocket non persistées plutôt que d'être écrit sur disque ; la réponse vocale est en WAV PCM16 à 22050 Hz, suffisant pour de la parole et trois fois plus léger que du 44,1 kHz ; les échanges de contrôle sont en JSON, verbeux mais lisibles dans un artefact et vérifiables à la sonde. Les contrôles qualité sont intégrés aux flux et non ajoutés après : dans le flux C, la **relecture du fichier** avant complétion du job est le contrôle — le worker ne peut pas déclarer écrite une note absente ; dans le flux B, **GATE** décide avant l'appel et le journal d'audit ne conserve que des paramètres assainis ; dans le flux A, le **registre d'outils** refuse un outil non prévu au démarrage.

---

## SECTION 10 — Intégrer alertes et gestion des erreurs

**10.1 Mécanisme d'alerte et scénario de reprise** — **[PROUVE]** · joindre les trois captures `c2-avant` / `c2-pendant` / `c2-apres`

> **Mécanisme d'alerte.** *Déclencheur* : cinq sondes de santé interrogées en boucle toutes les **2 secondes** par Presence — Camunda `:8088`, pont Codex `:8765`, pont Claude `:8766`, accueil host-agent `:8001`, modèle local `:8090`. Un service qui ne répond pas dans le délai de 1,5 s fait basculer l'état de `UP` à `DEGRADED`. *Canal* : bandeau d'alerte dans Presence (contraste ≥ 4,5) et note écrite dans le coffre. *Destinataires* : l'utilisateur présent (bandeau) et l'équipe (note datée). L'annonce **vocale** de l'alerte est en P0 de la feuille de route : elle n'est pas encore branchée, et c'est cohérent avec le produit — dans un assistant mains libres, une alerte purement visuelle est une alerte manquée.
> **Scénario de reprise**, en trois temps : (1) **constater** — le bandeau nomme le service dégradé et l'interface continue de fonctionner en local, donc la séance ne s'arrête pas ; (2) **relancer** — une relance unique par script de reprise, comme écrit dans la procédure SKU10, au lieu de réparer en improvisant ; (3) **vérifier** — le retour à `UP` est constaté par la sonde, pas supposé. Mesures relevées lors de la démonstration C2 (coupe simulée du pont Codex vers `127.0.0.1:1`) : `UP` en **41 ms**, bascule `DEGRADED` en **1560 ms**, retour `UP` en **52 ms** ; 7 tests verts et trois captures datées.
> **Lien avec les risques de la section 3.** Ce mécanisme en clôture deux : « défaillance d'un service tiers » (repli local + alerte visible + note) et « note de santé erronée » (relecture avant complétion). Il rend en outre visible le risque d'exfiltration, puisque l'état d'appel distant reste affiché.

**10.2 Messages d'erreur** — **[PROUVE]**

> Trois exemples, tels qu'affichés à l'écran. (1) **Service dégradé** : le bandeau nomme le service et la conduite à tenir — il dit *quoi* et *lequel*, il n'accuse pas, et il est doublé d'un équivalent texte lisible grâce au contraste. (2) **« Canal pas encore prêt. »** : affiché quand l'utilisateur appuie sur la touche de parole avant l'ouverture du WebSocket (correctif C10) — sans ce message, l'appui tombe dans le vide sans explication. (3) **Pont indisponible** : l'outil annonce l'indisponibilité et poursuit en local, au lieu de produire une erreur brute ou un silence.
> Principe commun : jamais de trace technique ni de code d'erreur brut à l'utilisateur ; toujours un état **et** une conduite à tenir ; toujours le doublon texte/voix.

---

## SECTION 11 — Intégrer des services tiers, API et IA

**11.1 Services tiers** — **[PROUVE→CIBLE]**

> **Services intégrés.** (1) **Agents IA distants** via trois ponts HTTP : Codex `:8765`, Claude `:8766`, Qwen `:8767` — rôle : traiter ce que le cerveau local de 3 milliards de paramètres ne mène pas (analyse de code volumineuse, recherche approfondie). (2) **Recherche web** : SearXNG en local d'abord, puis chaîne de replis DuckDuckGo → Tavily → Brave → Exa → Jina → Serper. (3) **Camunda 8** `:8088` pour l'orchestration BPMN. (4) **Intégrations optionnelles à clé facultative**, livrées mais non branchées au parcours démontré : JeV pour l'entrée mains libres, StepAudio TTS pour une voix distante.
> **Paramétrage.** Un service n'est inscrit au registre d'outils **que si sa configuration est présente** : sans jeton, l'outil n'existe pas — il n'échoue pas en pleine conversation. Le cerveau local expose un contrat compatible OpenAI, la voix un contrat compatible OpenAI en WAV PCM16 : un fournisseur se remplace sans réécrire le host-agent.
> **Authentification et secrets.** Jeton **Bearer** par pont, lu exclusivement depuis l'environnement ; `.env.local` hors versionnage et monté en lecture seule dans le conteneur ; refus 401 prouvé par sonde en l'absence de jeton ; journal d'audit conçu pour ne conserver que des paramètres assainis (ADR-012). Les clés ayant été visibles en séance le 19/09 sont régénérées, et aucune clé n'apparaît dans une capture de ce dossier.
> **Justification au regard des contraintes.** Le distant est un complément, jamais le chemin par défaut : le RGPD impose que la voix et sa transcription restent sur le poste, le coût impose zéro abonnement par requête, la démonstration impose qu'une panne tierce n'arrête pas la séance. D'où le local-first avec escalade à la demande, et le choix de Camunda plutôt que d'un script : le flux reste modifiable sans redéploiement.

**11.2 Vérifications et impacts** — **[PROUVE]**

> *Vérifications techniques* : sondes de disponibilité avec réponse relevée le 19/09 sur `:8765` et `:8766` ; tests de registre avec et sans jeton (37 tests C1, 133 tests de régression sur les outils) ; chaîne de repli web couverte par 74 tests — **sur doubles, sans appel réseau réel**, ce qui est dit ici plutôt que présenté comme une validation en conditions réelles. *Sécurité* : refus 401 sans jeton, secrets hors versionnage, moindre privilège par la classification `danger="read"`, exposition d'écoute vérifiée dans le code et portée au plan de clôture. *Performance* : délai de sonde 1,5 s, boucle de 2 s, temps de réponse mesurés (41 ms en `UP`, 52 ms au retour). *Impacts environnementaux* : aucun appel distant par tour — la décision vient de l'utilisateur, ce qui borne mécaniquement la consommation ; modèles quantifiés sur un seul GPU grand public (7,3 Go/12) plutôt qu'une API par requête ; calcul arithmétique exécuté en local. *Impacts éthiques* : sortie de données rendue visible à l'écran, contenu externe traité comme non fiable, aucune délégation autonome — l'utilisateur reste décideur.

---

# PARTIE 2 — SOUTENANCE (15 min + 10 min)

## ÉTAPE 1 — Déroulé chronométré — **[PROUVE]**

| Temps | Séquence | Ce que le jury voit et entend |
|---|---|---|
| 0:00–1:30 | Contexte et cahier des charges | « Une équipe tech pilote plusieurs agents IA et perd du contexte entre les fenêtres. Contraintes éliminatoires : français, Windows, un GPU 12 Go, aucune voix dans le cloud. J'ai tenu le produit et la recette ; la réalisation est déléguée à des agents IA sous circuit de responsabilité outillé. » |
| 1:30–3:30 | Architecture et interopérabilité | Schéma C4 niveau 1. Trois choix, pas plus : (1) **local-first avec escalade à la demande** — RGPD, latence, coût ; (2) **une brique = un service sur son port** — EARS/BRAIN/MOUTH interchangeables, trois oreilles bancées en une journée ; (3) **Camunda BPMN** pour que le flux santé → note soit lisible par un non-développeur : c'est la partie low code. |
| 3:30–11:30 | **Démonstration en direct** | Le fil unique de l'ÉTAPE 2 |
| 11:30–13:30 | Sécurité, tests, qualité | Trois chiffres : **1105 tests passés**, **7,3 Go / 12 de VRAM**, **premier son ~1,1 s**. Puis : « la carte des modèles n'a pas été choisie sur catalogue mais à l'aveugle par l'utilisateur final, à volume égalisé » — la meilleure preuve que les choix sont les miens. |
| 13:30–15:00 | Évolutions et conclusion | P0 : tour vocal complet vers un pont externe, annonce vocale de l'alerte. P1 : recherche web en conditions réelles, première requête perdue, mots imposés Whisper, liaison à `127.0.0.1`. P2 : Hyper-Ambiant-XL. Conclusion : « le recadrage du 19 a supprimé le routeur d'escalade autonome — l'utilisateur décide du distant, c'est un choix produit, pas une limite technique. » |

## ÉTAPE 2 — Scénario de démonstration, un seul fil — **[PROUVE→CIBLE]**

| Étape | Ce que je montre à l'écran | Ce que je dis | Durée |
|---|---|---|---|
| **Parcours profil 1** (mains libres) | Presence au repos, alternative texte visible. J'appuie sur la touche de parole, je pose une question métier, je relâche. La transcription s'écrit, la réponse est dite **et** affichée. | « Profil 1 : aucune souris. La voix entre, la voix sort, le texte reste affiché en permanence — c'est l'alternative d'accessibilité. Tout se passe sur le poste : 0,45 à 0,7 seconde pour la transcription, 25 à 70 millisecondes pour le premier jeton, environ 1,1 seconde avant le premier son. » | 2:00 |
| **Parcours profil 2** (installation) | Assistant d'onboarding : bienvenue → touche de parole → masquage. Configuration écrite localement. | « Profil 2 : quelqu'un qui installe. Trois étapes, tout au clavier, configuration stockée en local, 32 tests sous Windows. » *(si le live est risqué : les 3 captures datées)* | 1:00 |
| **Flux de bout en bout** | Une opération qui passe par l'outil `calculer`, puis une question qui montre l'identité produit. | « Flux A exécuté de bout en bout : micro → EARS → BRAIN → MOUTH → écran et haut-parleur. Le modèle local se trompe en calcul mental, donc j'ai ajouté un outil de calcul déterministe en local : 30 tests, aucun appel réseau. Choix de sobriété autant que de fiabilité. » | 2:00 |
| **Alerte + reprise** *(obligatoire)* | **Je coupe le pont Codex** (URL vers `127.0.0.1:1`). Le bandeau apparaît en ~1,5 s et nomme le service. États avant / pendant / après. Je relance par le script de reprise, le bandeau repasse au vert. | « Cinq sondes toutes les deux secondes, délai de 1,5 seconde. Le service tombe : l'état passe de UP à DEGRADED, le bandeau s'affiche à un contraste supérieur à 4,5 — WCAG AA — et l'application continue de tourner en local, donc la séance ne s'arrête pas. Reprise : une seule relance par script, comme dans ma procédure d'incident, pas de bricolage en direct. Retour UP constaté par la sonde en 52 millisecondes. Une note est écrite dans le coffre, et le worker la relit avant de finir son job. » | 2:30 |
| **Service tiers** *(obligatoire)* | Je demande explicitement une délégation à Claude via `:8766`. L'état « appel distant » s'affiche. Réponse en texte et en voix. Puis je montre le registre au démarrage : `OUTILS: ask_claude, ask_codex, web_search`. | « Le distant n'est appelé que si je le demande, derrière une porte d'autorisation, avec un jeton lu depuis un fichier hors versionnage. Sans jeton, l'outil n'existe pas au démarrage — il n'échoue pas en pleine conversation, et la sonde sans jeton renvoie 401. La sortie de données est affichée à l'écran : je vois toujours ce qui quitte le poste. » | 2:30 |

**Plan B, étape par étape** — **[PROUVE]**

- *Profil 1 muet* → captures `cursor-ui-5-parole.png` + `-6-distant.png`, et je commente les mesures du test live du 19/09.
- *Onboarding qui ne démarre pas* → les 3 captures datées du parcours.
- *Première requête perdue* (bug connu, non fermé) → **je le dis** et je répète la phrase : « défaut connu, la lane C10 a livré un correctif partiel, la piste restante est le mode de lancement de l'application. » L'honnêteté marque des points, l'improvisation non.
- *Alerte qui ne se déclenche pas* → captures `c2-avant/pendant/apres.png` + les mesures (41 ms / 1560 ms / 52 ms).
- *Pont tiers injoignable* → c'est exactement le scénario d'alerte : je bascule dessus et je montre le repli local.
- *GPU saturé* → ne charger **aucun** modèle hors profil ; procédure SKU10 : contrôles, une relance unique, puis escalade.

## ÉTAPE 3 — Les 8 questions du jury, une phrase chacune — **[PROUVE]**

1. **Pourquoi cette plateforme plutôt qu'une autre ?** → Camunda 8 parce que le flux doit rester modifiable par un non-développeur et que son modeleur BPMN porte déjà les reprises (3 tentatives par tâche) ; et MOTHER en code parce qu'aucune plateforme no code du marché ne tient un assistant vocal français sur un GPU 12 Go sans envoyer l'audio dans le cloud.
2. **Si vous étiez en groupe, qu'avez-vous fait vous-même ?** → Projet individuel : j'ai tenu le périmètre, les arbitrages et la recette, et j'ai délégué la réalisation à des agents IA sous circuit de responsabilité outillé où chaque tâche produit un artefact et un code de retour — un de leurs commits est même signé par l'agent, en `d1c9f0d`.
3. **Que se passe-t-il si le service tiers tombe ?** → Cinq sondes le détectent en moins de deux secondes, un bandeau le nomme, l'application bascule sur le local, et une relance unique par script la ramène au vert — c'est la démonstration que je viens de faire.
4. **Comment votre solution respecte-t-elle le RGPD ?** → La voix est traitée et non conservée sur le poste, les secrets sont hors versionnage, la sortie vers un tiers n'a lieu qu'à la demande explicite et s'affiche à l'écran — et je précise que base légale, notice et procédure d'effacement restent à formaliser avant un usage réel.
5. **Comment un utilisateur en situation de handicap utilise vos interfaces ?** → Soit tout à la voix, soit tout au clavier avec le texte affiché en permanence : Tab parcourt, Entrée active, la touche de parole se maintient, et les contrastes mesurés vont de 6,1:1 à 14,3:1.
6. **Que disent vos tests de performance et d'accessibilité ?** → Performance : environ 1,1 s avant le premier son, 7,3 Go de VRAM sur 12, 1105 tests passés ; accessibilité : contrastes et navigation clavier mesurés, validation avec lecteur d'écran non faite — je le dis au lieu de la prétendre.
7. **Comment déployez-vous une évolution sans couper le service ?** → Branches avec suites de tests avant fusion, bascules par configuration pour tout ce qui est risqué, retour arrière au commit précédent — et le local-first garantit qu'un composant distant en panne ne coupe pas la voix.
8. **Que feriez-vous avec un mois de plus ?** → Prouver le tour vocal complet vers un pont externe en conditions réelles, brancher l'annonce vocale de l'alerte, valider la chaîne de recherche web sur réseau réel, résoudre la première requête perdue.

## ÉTAPE 4 — Checklist de la veille — **[PROUVE]**

- ☐ Scénario chronométré **deux fois**, bouclé sous 14 minutes. En cas de dépassement, couper dans la présentation, **jamais** dans les deux démonstrations obligatoires.
- ☐ **Relancer les suites de tests** sur le poste du jour J et dater le chiffre annoncé — 1105 passés est une mesure du 19/09, une mesure historique ne remplace pas une exécution récente.
- ☐ Contrôles SKU10 sur le poste réel : conteneur démarré, santé `:8090`, santé `:8001`, Presence visible, VRAM ≤ 10 Go.
- ☐ Jetons présents dans `.env.local`, **clés du 19/09 régénérées**.
- ☐ Captures de secours ouvertes une par une une fois : `ui-1` à `ui-9` + `c2-avant/pendant/apres` — **aucun secret, aucun chemin personnel**.
- ☐ Vérifier le réseau du lieu : les ponts sont locaux, Camunda et les replis web ne le sont pas tous.
- ☐ Décision prise sur l'écoute du host-agent : soit corrigée (`127.0.0.1`), soit écrite telle quelle au §3.1 avec sa mesure corrective. Ne pas laisser le sujet hors du dossier.
- ☐ Dossier enregistré en `.docx` ou exporté en `.pdf`, **déposé avant la date limite de la convocation**.

---

# Les 8 phrases qui ferment un trou (à coller là où le doute existe)

| Où | Si on ne peut pas prouver, écrire exactement ça | Marque |
|---|---|---|
| En-tête, plateformes | « Camunda 8 porte l'orchestration en BPMN modélisable ; le composant IA local est développé parce que ses contraintes ne sont couvertes par aucune plateforme no code du marché. » | [PROUVE] |
| §2.2, §9.1 (Camunda) | « Le processus BPMN et le worker sont livrés et testés, avec relecture du fichier avant complétion ; le déploiement et la planification de bout en bout seront rejoués au plan de clôture. » | [CIBLE] |
| §4.1 T2, §11.1 (tour vocal distant) | « Le registre et l'authentification Bearer sont prouvés par 37 tests et par sonde (401 sans jeton, 200 avec) ; la démonstration en direct montre la délégation demandée par l'utilisateur. » | [CIBLE] |
| §3.1, §3.2 (réseau) | « Le host-agent écoute sur toutes les interfaces avec un secret exigé à chaque requête et un port non publié ; la liaison à `127.0.0.1` est une mesure corrective inscrite au plan de clôture. » | [PROUVE] |
| §3.1, §5.2 (audio) | « Aucun audio n'est persisté dans la voie nominale, vérifié par lecture de code le 20/09 ; la politique de conservation reste à formaliser. » | [PROUVE→CIBLE] |
| §4.1 T6, §8.2, question 6 (accessibilité) | « Contrastes mesurés et navigation clavier conçue dans l'interface ; validation avec un lecteur d'écran non réalisée. » | [CIBLE] |
| §4.2, plan B (1re requête) | « Défaut intermittent en début de séance ; le correctif C10 réduit le cas (appui avant ouverture du WebSocket), la piste restante est le mode de lancement. » | [PROUVE] |
| §11.2 (recherche web) | « 74 tests sur doubles, sans appel réseau réel ; l'instance locale rend actuellement zéro résultat à cause de CAPTCHA moteurs. » | [PROUVE] |

---

# Ne pas coller, sous aucun prétexte

1. Aucune valeur de secret, de jeton ou d'URL de fournisseur — y compris dans une capture, un log collé ou un extrait de fichier. Le host-agent porte un secret de développement **en dur** dans `dev/scripts/serve_hostagent.py` : citer l'existence du secret est acceptable, recopier sa valeur non.
2. Tout chemin personnel absolu, tout nom de machine, toute adresse e-mail — relire chaque capture avant insertion (bloc §8.1).
3. « Bouton de retour utilisateur → issue GitHub lue automatiquement une fois par jour » : le bouton ouvre bien un formulaire d'issue sur action humaine (`native/presence/onboarding.py`, `ouvrir_feedback`), **la lecture automatisée des retours n'existe pas**.
4. « Les services écoutent uniquement sur `127.0.0.1` » : faux pour le host-agent, non mesuré pour les ponts. Utiliser la ligne réseau du tableau ci-dessus.
5. « Recherche web validée en conditions réelles » : 74 tests sur doubles, aucun réseau réel appelé.
6. « Testé avec un lecteur d'écran » : non fait.
7. Des chiffres RICE (reach/impact/confidence/effort) : la priorisation reste qualitative.
8. Un `[P]`, un `TODO`, un `{{…}}` ou une note de lane qui aurait fuié dans le corps du dossier.

---

# Clôture de lane

- Blocs issus du PREFILL du 20/09 (~10:50) et de l'OUT `TAQUET-ANNEXE` de Claude (11:05) ; les faits « code » (port d'écoute, contrastes, bouton de retour) ont été **revérifiés dans le dépôt** le 20/09 avant d'être marqués `[PROUVE]`, et le journal de versions a été rempli depuis `git log` (le trou D-13 est donc fermé).
- Ce fichier est une **aide à coller** : les cases sont rédigées par Thomas, à sa voix.
- Lane `BGB-AIDE` (complexité **simple** → notification OC + ponts). Clôture : `python dev/scripts/account.py close --lane BGB-AIDE --status done` — **non exécutée ici**, le périmètre de cette lane était l'écriture du fichier.
- Ce fichier ne contient **aucun secret**. Les clés montrées en séance le 19/09 restent à régénérer avant tout dépôt public.
