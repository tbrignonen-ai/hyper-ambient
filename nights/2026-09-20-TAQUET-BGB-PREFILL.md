---
date: 2026-09-20
heure: ~10:50
type: dossier-bgb-prefill
lane: BGB-AIDE
auteur: Qwen — suggestions ; **Thomas écrit les cases**
sources: ["BGB_BC02_Dossier_technique_a_completer.docx", "BGB_BC02_Preparer_votre_soutenance.docx", "[[2026-09-19-CARTE-FIGEE]]", "[[2026-09-19-ANNEXE-TECH-HYPER-AMBIANT]]", "[[2026-09-19-SUGGESTIONS-CASES-BGB]]", "[[2026-09-20-MAKINGOF-ACCOUNTABILITY]]"]
regle: n'écrire que ce qui est vrai ET démontrable lundi. `[P]` = à prouver avant d'écrire.
---

# TAQUET 1H — Pré-remplissage des cases BC02 (dossier + soutenance)

## Mode d'emploi (3 règles)

1. **Copier-coller autorisé.** Les blocs `> PRÊT À COLLER` sont rédigés dans le format et la longueur attendue par la case. Thomas reformule à sa voix, ne recopie pas aveuglément : le jury vérifie que « le travail est le vôtre ».
2. **`[P]` = à prouver.** Une affirmation marquée `[P]` ne doit PAS être écrite telle quelle dans le dossier. Utiliser la **reformulation « cible »** du § D (elle dit la même chose sans mentir).
3. **Périmètre figé 0.1** : Windows · **FR par défaut + EN 0.1 inclus** (`HA_LANG=en`) · local-first · 1 GPU 12 Go · carte modèles figée le 19/09. Ne pas promettre Mac, ES, ni Hyper-Ambiant-XL comme livré : c'est la roadmap §6.

---

## A. En-tête « Votre projet »

**Nom du candidat** : Thomas *(à compléter)*
**Cohorte et groupe projet** : *(à compléter)* — laisser vide si travail seul, mais voir §A3 : la flotte d'agents IA doit être déclarée dans « contributions personnelles », pas dans « groupe ».

**Cas traité** — > PRÊT À COLLER
> Assistant vocal mains libres pour une petite équipe technique : pilotage à la voix d'outils et d'agents IA (recherche, délégation, calcul, supervision), avec traitement local par défaut et données qui restent sur le poste. Cas d'organisation, pas un projet personnel : la même équipe coordonne plusieurs agents IA (Cursor, Codex, Claude, Qwen) et a besoin d'un point d'entrée unique, audible, sans ouvrir dix interfaces.

**Plateformes no code/low code utilisées** — > PRÊT À COLLER *(point de tension assumé, voir §D-0)*
> **Camunda 8** pour l'orchestration : processus BPMN `night_health_vault_note` modélisé graphiquement (départ nocturne → `health-check` → `vault-note` → fin, 3 tentatives par tâche) et exécuté par un worker branché en REST v2. C'est la partie no code/low code de la solution : le flux est lisible et modifiable par un non-développeur dans le modeleur. **Hyper Ambient (MOTHER)** est le composant IA local intégré comme service dans ce flux : il est développé en code, assumé comme tel, parce que les contraintes (français, Windows, 12 Go de VRAM, RGPD, aucun audio dans le cloud) ne sont pas couverts par les plateformes no code du marché.

---

## B. Sections 1 à 11 — case par case

### SECTION 1 — Modéliser l'architecture fonctionnelle

**Contexte du cas (organisation, besoins métiers, contraintes)** — 5 à 10 lignes au total avec le rôle
> Une équipe technique de petite taille pilote plusieurs agents IA en parallèle et perd du contexte entre les outils : chacun a son interface, ses jetons, ses fenêtres. Le besoin métier est un point d'entrée unique et mains libres — parler, entendre, voir l'état — pour superviser, rechercher et déléguer sans quitter son poste. Les contraintes du cahier des charges sont éliminatoires : français (et anglais en option), Windows natif, un seul GPU grand public à 12 Go partagé, confidentialité des conversations (RGPD, aucune sortie cloud par défaut), sobriété numérique, et démonstration clé-en-main reproductible.

**Votre rôle et vos contributions personnelles**
> Projet individuel. J'ai tenu le rôle de produit et de recette : définition du périmètre, arbitrage des choix techniques, tests en conditions réelles, et validation finale de la carte des modèles. Une partie de la réalisation a été déléguée à des agents IA (Cursor pour le code, Codex pour les lanes documentaires et overflow, Claude pour le lead technique et l'arbitrage, Qwen pour la préparation dossier). **Cette délégation est outillée et contrôlée** : chaque tâche est une lane ouverte/fermée dans un circuit de responsabilité (`dev/scripts/account.py`), avec artefact de sortie obligatoire (OUT), code de retour (EXIT) et notification — « open sans close = fuite ». Ce que je signe : les décisions, les mesures, les recettes.

**1.1 Schéma d'architecture (C4, ≥4 composants)**
Reprendre les deux diagrammes Mermaid de l'annexe §2 (niveau 1 contexte + niveau 2 conteneurs) — ils font déjà ≥4 composants et incluent SI existant + services tiers. Légende à coller :

> **Légende.** *Poste Windows* : **Presence** (interface appuyer-pour-parler, affiche transcription, réponse et état d'appel distant) · **ponts d'agents** Codex `:8765`, Claude `:8766`, Qwen `:8767` (HTTP JSON, jeton Bearer) · **coffre Obsidian** (notes Markdown). *Runtime Hyper Ambient* : **host-agent** `:8001` (WebSocket audio/événements) qui compose **EARS** (Whisper large-v3, oreille) → **BRAIN** (Granite 4.2 3B sur `:8090`, cerveau local) → **MOUTH** (Magpie TTS Sofia sur `:8092`, voix), plus **GATE** (porte d'autorisation, `GATE_MODE`, journal d'audit). *Services tiers* : **SearXNG** local et chaîne de repli web (DuckDuckGo, Tavily, Brave, Exa, Jina, Serper) · agents distants accessibles uniquement par outil autorisé. *Orchestration* : **Camunda 8** `:8088` ↔ **worker** (jobs `health-check` puis `vault-note`).

**1.2 Justification des choix** — 3 à 6 lignes
> Local d'abord pour trois raisons métier : confidentialité (la voix et sa transcription ne quittent pas le poste), latence (premier jeton 25 à 70 ms, premier son ~1,1 s) et coût (aucun abonnement par requête). Le distant n'est pas supprimé mais mis sous contrôle : il n'est appelé que par un outil explicitement autorisé par l'utilisateur, derrière la porte GATE, et l'interface affiche l'état d'appel distant. Le BPMN Camunda rend l'automatisation lisible par un non-développeur, ce qu'un script Python ne permet pas. Ce schéma a dicté la configuration : chaque brique est un service sur `127.0.0.1` avec son propre port, donc remplaçable sans toucher au reste (c'est ce qui a permis de changer trois fois de modèle d'oreille en une journée).

### SECTION 2 — Organiser l'interopérabilité avec le SI

**2.1 Table d'interopérabilité** — un système par ligne

| Système connecté | Sens des échanges | Protocole / API | Format de données | Authentification |
|---|---|---|---|---|
| Presence (UI Windows) ↔ host-agent | Bidirectionnel, déclenché par appui PTT | WebSocket `:8001` | Trames audio + événements JSON (transcription, réponse, état distant) | Secret de transport côté host-agent |
| host-agent → BRAIN local | Requête/réponse à chaque tour | HTTP `:8090` (llama-server, compatible OpenAI) | JSON, texte | Aucune (localhost uniquement) |
| host-agent → MOUTH | Synthèse à chaque réponse | HTTP `:8092` (`nemo-speech serve`) | WAV PCM16 22050 Hz | Aucune (localhost) |
| host-agent → pont Codex / Claude / Qwen | Sur décision utilisateur, via outil `ask_*` | HTTP `POST /ask` `:8765` / `:8766` / `:8767` | JSON | **Jeton Bearer**, lu depuis `.env.local` (hors git, monté en lecture seule) |
| host-agent → SearXNG + replis web | Sur appel de l'outil de recherche | HTTP JSON | JSON (`results[]`) | Aucune pour l'instance locale ; clés par fournisseur pour les replis |
| Camunda 8 ↔ worker | Activation et complétion de jobs | REST API v2 | JSON | URL configurable ; détail d'authentification `[P]` |
| worker → coffre Obsidian (GED légère) | Après `health-check` | Écriture puis **relecture** d'un fichier | Markdown daté `YYYY-MM-DD-HEALTH.md` | Droits du système de fichiers |
| GitHub | Retours usagers (issues) | API / interface | Markdown | `[P — le bouton feedback existe-t-il vraiment ?]` |

**2.2 Justifications, points critiques, continuité** — 6 à 10 lignes
> *Choix.* HTTP/JSON partout plutôt que des SDK propriétaires : c'est vérifiable à la sonde, remplaçable, et lisible dans un OUT. Le WebSocket pour Presence parce qu'il faut du duplex temps réel (trames audio montantes, états descendants). Markdown pour le coffre parce que c'est le format natif d'Obsidian, pérenne et accessible sans outil.
> *Point critique 1 — registre d'outils.* Un outil n'est exposé que si son prérequis de configuration existe ; une vérification compare outils actifs et outils attendus et **refuse un outil non prévu**. Traitement : une configuration incomplète se traduit par l'absence de l'outil, pas par un échec en pleine conversation. Preuve : C1 — la cause racine était que `docker start` ne recharge pas `.env.local` ; le chargeur livré donne `OUTILS: ask_claude, ask_codex, web_search` au démarrage, 37 tests verts.
> *Point critique 2 — health/note.* Le worker traite `health-check`, produit des variables d'état, puis `vault-note` écrit le Markdown **et le relit avant de compléter le job** : impossible d'annoncer une note écrite qui ne l'est pas. Le BPMN porte 3 tentatives par tâche.
> *Continuité.* Chaque brique est un service indépendant : tomber un pont ne coupe ni la voix ni le cerveau local (démonstration C2). Reprise documentée par la procédure SKU10 : contrôles avant démo (conteneur, `:8090`, `:8001`, Presence, budget VRAM), puis **une relance unique par script** plutôt qu'une succession de réparations improvisées. Compatibilité technique : mêmes contrats OpenAI-compatibles pour le cerveau et la voix, donc un modèle peut être remplacé sans réécrire le host-agent.

### SECTION 3 — Évaluer les risques de sécurité

**3.1 Tableau d'analyse de risques** (≥3 catégories, avec référence à chaque ligne)

| Risque identifié | Catégorie d'exposition | Mesure corrective ou de contournement | Référence |
|---|---|---|---|
| Jeton de pont divulgué (Codex/Claude/Qwen) | Accès et droits | Jetons lus depuis l'environnement uniquement, `.env.local` hors versionnage et monté en lecture seule ; refus 401 sans jeton prouvé par sonde ; rotation à planifier ; journal d'audit assaini (ADR-012, aucun secret) | RGPD art. 32 · ANSSI guide d'hygiène |
| Agent distant agissant au-delà de la demande | Accès et droits | Porte GATE centralise la décision (`GATE_MODE` : `plan`, `ask`, `manual`, `auto`, `build`, `troubleshoot`) ; outils classés `danger="read"` ; passer en `GATE_MODE=ask` resserre sans modifier le code | ISO 27001 A.9 (moindre privilège) |
| Host-agent exposé sur le réseau | Exposition des API | Écoute locale, code avertissant de ne pas exposer hors machine avec un secret de développement ; ponts en `127.0.0.1` `[P — à vérifier par capture `netstat` avant d'écrire]` | ANSSI · charte SSI |
| Injection de prompt via contenu web ou réponse d'agent | Exposition des API / services tiers | Contenu externe traité comme non fiable ; GATE décide, pas le modèle ; validation humaine avant toute action ; registre limité aux outils configurés | OWASP LLM Top 10 (LLM01 prompt injection) |
| Conservation de la voix ou des transcriptions | Stockage des données | Audio non conservé `[P]` ; traitement local par défaut ; durée de conservation, base légale, notice d'information et procédure d'effacement **à formaliser** | RGPD art. 12-17, 25, 32 |
| Défaillance d'un service tiers (pont coupé, SearXNG sans résultat) | Vulnérabilité des services tiers | Repli local automatique + bandeau d'alerte visible + note de coffre (démo C2) ; chaîne de repli multi-fournisseurs pour la recherche web | ISO 27001 A.17 (continuité) |
| Surcharge GPU (12 Go partagés) | Disponibilité | Budget VRAM mesuré à 7,3 Go/12 au repos dans le profil figé ; interdiction de charger un modèle hors profil sans arbitrage ; composants hors profil explicitement listés | Procédure interne SKU10 |
| Note de santé erronée ou incomplète | Intégrité des données | Écriture suivie d'une relecture dans le worker ; droits du coffre à formaliser `[P]` | RGPD art. 32 |

**3.2 Méthode et constats** — 3 à 5 lignes
> Méthode : grille de cotation vraisemblance × impact à quatre niveaux, croisée avec deux référentiels — OWASP LLM Top 10 pour les risques propres aux applications à base de modèles (injection de prompt, exfiltration via outil) et RGPD articles 25/32 pour la protection dès la conception. Principaux écarts relevés : (1) la documentation de conformité RGPD est incomplète — il manque base légale, notice d'information, durée de conservation et procédure d'effacement ; (2) l'exposition réseau réelle des services n'a pas été vérifiée par une mesure, seulement par une convention de code ; (3) la rotation des jetons n'est pas outillée. Aucun de ces écarts n'est bloquant pour une démonstration locale, tous sont à traiter avant un usage réel en organisation.

### SECTION 4 — Mettre en œuvre le plan de tests

**4.1 Plan de tests** — 3 fonctionnels + 2 techniques + accessibilité + performance

| N° | Scénario testé | Type | Critère de réussite | Outil | Résultat |
|---|---|---|---|---|---|
| T1 | Dialogue vocal local simple : PTT → transcription → réponse → voix | Fonctionnel | Réponse audible en français, transcription exacte, rien ne sort du poste | Stack réelle figée, voix de Thomas, captures | **Fait** au test live du 19/09 : oreille 0,45–0,7 s/phrase, 1er jeton 25–70 ms, premier son ~1,1 s. Noms propres justes (Camunda, Lefebvre, Codex), nombres justes (« 8376 divisé par 2,8 »). Réserve : la 1re requête d'une séance est parfois perdue |
| T2 | Consultation d'un agent distant à la demande de l'utilisateur | Fonctionnel | Outil appelé, annonce vocale/visuelle de l'appel distant, réponse restituée | Registre d'outils + ponts `:8765`/`:8766`, log `OUTILS:` | **Partiel** : chargement des clés et registre prouvés (37 tests, C1) ; tour vocal complet vers pont externe `[P]` |
| T3 | Parcours d'onboarding en 3 étapes (bienvenue, PTT, masquage) | Fonctionnel | Assistant mené au bout, configuration locale écrite | `native/presence/onboarding.py`, tests Presence | **32/32 verts sous Windows** (santé + premier tour inclus) ; parcours live filmé `[P]` |
| T4 | Suites automatisées du dépôt | Technique | Aucune régression sur le périmètre figé | pytest, conteneur `mother-core-dev` | **1105 passés, 11 ignorés, 2 échecs** (19/09 ~20h). Les 2 échecs sont les tests Presence natifs Windows, verts sous Windows (32/32). **À relancer la veille de la soutenance** |
| T5 | Outils avec et sans jeton | Technique | Outil absent si jeton absent ; sonde refusée 401 sans jeton, 200 avec | `test_outils_voix.py`, `test_codex_bridge.py`, `test_clibridge.py`, `test_gate_more_edges.py` | Registres et sondes 401/200 consignés ; exécution du jour `[P — recoller la sortie]` |
| T6 | Accessibilité : navigation clavier, texte affiché, contraste de l'alerte | Accessibilité | Tout le parcours réalisable sans souris ; bandeau lisible en basse vision ; alternative texte permanente à la voix | Parcours Tab/Entrée sur Presence ; calcul de contraste du bandeau | **Contraste prouvé** : bandeau d'alerte `#7a1212` sur `#fff8e8`, ratio ≥ 4,5 (WCAG AA). Navigation clavier prévue par le design (Tab parcourt, Entrée active, PTT maintenable). Mesure en situation avec lecteur d'écran `[P]` |
| T7 | Performance : délai avant le premier son et empreinte mémoire GPU | Performance | Premier son < 2 s sur phrase courte ; VRAM ≤ 10 Go | Mesures horodatées au test live du 19/09, profil figé | **Atteint** : ~1,1 s phrase courte (3,2–4,8 s phrase longue ou à nombres) ; **VRAM 7,3 Go / 12** au repos (cerveau + oreille + voix + Windows), marge ≈ 2,7 Go. Gain C9 : TTFA voix 4473,2 ms CPU → 1341,1 ms CUDA (−70 %) |

**4.2 Analyse des résultats** — 3 à 5 lignes
> Les tests ont révélé quatre vrais bugs, tous corrigés et datés : hachurage audio résolu par rééchantillonnage (6 sept) ; accent britannique résolu par passage à une voix FR native (8 sept) ; interruption non prise en compte au bouton (15 sept) ; outils absents au démarrage parce que `docker start` ne recharge pas `.env.local`, résolu par un chargeur dédié (19 sept, C1). Deux enseignements de méthode : les chiffres ont fait tomber des candidats mieux notés à l'oreille — Whisper large-v3 a été retenu sur mesure (0,42–0,57 s/phrase) et non sur réputation ; et un modèle peut être excellent et inutilisable ici (Canary-1b-v2 : 0,14–0,28 s à chaud mais pic VRAM 11712 MiB sur un budget de 12 Go). Reste ouvert : la première requête d'une séance parfois perdue, dont le correctif C10 n'a pas suffi.

### SECTION 5 — Garantir la qualité et la conformité continue

**5.1 Dispositif de suivi** — 3 à 6 lignes
> Trois boucles, à trois fréquences. **Quotidienne** : processus BPMN `night_health_vault_note` — contrôle de santé des services puis écriture d'une note Markdown datée dans le coffre, relue avant complétion ; responsable : le worker, relecture humaine par moi. **À chaque tâche** : circuit de responsabilité des lanes — `account.py open/pulse/close/scan`, journal `ACCOUNTABILITY-LEDGER.jsonl`, tableau `ACCOUNTABILITY-BOARD.md`, artefact OUT obligatoire et code EXIT ; responsable : OC pour l'horloge et le routage, OG pour le kanban. **À chaque évolution** : suites pytest avant fusion, branche git, note datée dans `nights/` ; responsable : moi. Le tableau de bord distingue deux régimes de notification : tâche simple → OC et ponts ; tâche complexe → OG qui informe OC.

**5.2 Trois volets de conformité**

| Volet | Votre ou vos mesures | Fréquence et responsable |
|---|---|---|
| Réglementaire : RGPD, gouvernance des données | Traitement local par défaut, audio non conservé `[P]` ; secrets hors versionnage (`.env.local`, lecture seule) ; journal d'audit sans secret (ADR-012) ; à compléter : base légale, notice d'information, durée de conservation, procédure d'effacement | À chaque évolution du registre d'outils ; responsable : Thomas |
| RSE et sobriété numérique | Modèles quantifiés et dimensionnés pour un GPU grand public (2,24 Go + 2,9 Go + 449 Mo + 79 Mo) ; 7,3 Go/12 au repos ; appel distant **seulement à la demande**, jamais à chaque tour ; l'outil `calculer` local évite un appel réseau pour une opération arithmétique | Contrôle VRAM à chaque changement de carte ; responsable : Thomas |
| Accessibilité numérique | Usage 100 % voix possible, et alternative texte permanente (transcription, réponse, état d'appel distant affichés) ; navigation clavier (Tab/Entrée/PTT maintenable) ; contraste du bandeau d'alerte ≥ 4,5 (WCAG AA) ; assistant d'onboarding en 3 étapes | À chaque modification d'interface ; mesure en situation `[P]` ; responsable : Thomas |

**5.3 Retours d'usage et traitement des écarts** — 2 à 4 lignes
> Deux canaux aujourd'hui. **Canal interne outillé** : les retours d'usage sont les lanes du circuit de responsabilité — un écart constaté ouvre une lane avec OUT attendu, et sa clôture produit une preuve horodatée (journal JSONL) ; c'est ainsi qu'un bug intermittent signalé à l'usage (première requête perdue) est devenu la lane C10 avec son test de reproduction. **Canal utilisateur final** : le protocole de dégustation du 19/09 — l'utilisateur final note à l'aveugle, à volume égalisé, sur ses propres enregistrements ; c'est lui qui a tranché la carte des modèles, pas les classements publics. *Ne pas écrire* « bouton feedback → issue GitHub lue 1×/jour » tant que `[P]` n'est pas vérifié (voir §D-5).

### SECTION 6 — Organiser les évolutions sans rupture de service

**6.1 Feuille de route** (priorisation RICE **qualitative** — ne pas inventer de chiffres)

| Évolution envisagée | Priorité | Effets attendus | Continuité de service |
|---|---|---|---|
| Prouver le tour vocal complet vers un pont externe (C1 live) | **P0** — impact élevé, confiance moyenne, effort moyen | Le jury voit une interopérabilité réelle, pas seulement des tests | Aucune coupure : la lane est additive, le repli local reste actif |
| Brancher l'annonce vocale de l'alerte (aujourd'hui visuelle seule) | **P0** — impact élevé, effort faible | Alerte perceptible sans regarder l'écran, cohérente avec le mains libres | Feature flag : le bandeau reste si la voix échoue |
| Intégration des fournisseurs web réels (C4 en conditions réelles) | **P0** — le symptôme « rien trouvé » est ouvert | Recherche réellement utilisable, SearXNG + 6 replis | Chaîne de repli : un fournisseur hors service passe au suivant sans interrompre le tour |
| Résoudre la première requête perdue (C10/C13, piste `pythonw`) | **P1** | Fiabilité perçue en début de séance | Correctif côté lancement d'application, pas de changement de contrat |
| Câbler les mots imposés Whisper dans EARS (validés au banc, non branchés) | **P1** | Meilleure reconnaissance des noms propres métiers | Paramètre de configuration, repli sur le comportement actuel |
| Version EN au-delà du 0.1 (persistance de la locale dans `presence.json`, statuts WebSocket traduits) | **P1** | Ouverture aux utilisateurs non francophones | Bascule par variable d'environnement, FR reste le défaut : aucun impact sur l'existant |
| Version Mac | **P1** | Élargissement du parc | Portage du host-agent natif ; l'étude C7 (portage natif Windows sans Docker) fournit le patron |
| Packager proprement le binaire CUDA de `nemo-speech` | **P1** — réserve 1 de la carte figée | Installation reproductible, plus de binaire emprunté à un banc de test | Installeur signé (WiX Burn) avec manifestes SHA-256 des modèles |
| Hyper-Ambiant-XL (~20 Go VRAM) | **P2** — impact potentiellement élevé, confiance faible, effort élevé | Qualité de cerveau et de voix supérieure | Nouveau profil de configuration, l'ancien reste livré |
| Routeur déterministe local (fin de tour, détection d'adresse, interruption) | **P2** | Confort mains libres | **Recadrage acté** : aucun routeur d'escalade autonome — l'utilisateur décide du distant |

**6.2 Justification des priorités** — 3 à 5 lignes
> L'ordre suit deux objectifs : ce que le jury doit voir lundi (P0 = les deux démonstrations obligatoires, alerte/reprise et service tiers), puis ce qui conditionne un usage réel en organisation. Le dispositif de continuité repose sur trois mécanismes déjà en place : **déploiement progressif** par branches git avec suites de tests avant fusion ; **feature flags** pour tout ajout risqué (langue, backend de voix, porte GATE) — on change de comportement par configuration, sans réécrire le code ; **retour arrière** = revenir au commit précédent et relancer le service, le local-first garantissant que la coupure d'un composant distant ne coupe pas la voix. Chaque modèle retenu a un repli documenté (cerveau : NeoHorse-1-9B puis Ministral-3-8B ; oreille : Parakeet-TDT-0.6B-v3 ; voix : Supertonic F5 sur CPU, 0 VRAM).

### SECTION 7 — Documenter les évolutions et garantir la traçabilité

**7.1 Documentation**

*Extrait à insérer* : prendre **ADR-012** (séparation noyau conteneurisé / host-agent natif, et absence de secret dans le journal d'audit) dans `ARCHITECTURE.md`, ou à défaut le tableau de symptômes/réponses de la procédure `nights/2026-09-18-SKU10-PANNE.md` (plus parlant pour un jury : « host-agent ne répond pas au PTT → relance contrôlée du routeur »).

> **Où la documentation complète est hébergée** : dépôt GitHub (branche `nuit/2026-08-27`) pour le code, `ARCHITECTURE.md`, `STACK.md`, `STATUS.md` et les ADR ; coffre Obsidian pour les notes datées `nights/` (briefs, OUT, arbitrages, procédures d'incident) qui servent de bus documentaire entre les rôles. Chaque assertion factuelle de l'annexe technique porte une référence `[S…]` qui pointe vers une ligne de code, une note datée ou un commit.
>
> **Accessibilité des formats** : documentation en Markdown structuré par titres hiérarchiques (navigable au lecteur d'écran et convertible), tableaux à en-têtes explicites, diagrammes Mermaid **doublés d'une légende textuelle** pour ne pas perdre l'information en cas de rendu absent, aucune information portée uniquement par la couleur (le bandeau d'alerte combine couleur, texte et contraste ≥ 4,5), et alternative texte systématique à toute sortie vocale dans l'interface.

**7.2 Journal de versions** — à compléter avec `git log` récent ; base disponible :

| Version | Date | Modification apportée | Auteur |
|---|---|---|---|
| `779bc4c` | *(date à tirer de git log)* | Camunda : worker de santé et outillage de recette | *(auteur)* |
| `83d51f3` | | BRAIN : outils et recherche SearXNG | |
| `99756d9` | | Presence : interruption, onboarding et fenêtre | |
| `4f87024` | | UI Presence et harnais Codex/Claude | |
| `708ca31` | 2026-09-19 | Documentation de clôture de sprint (WRAP 20:50) | Thomas |
| `cff390e` | 2026-09-19 | Carte des modèles figée + environnement (SSD E:) | Thomas |

### SECTION 8 — Concevoir les interfaces accessibles

**8.1 Écrans principaux** — plateforme : **application Windows native « Presence »** (Python), adossée au runtime conteneurisé.
Captures disponibles : `nights/2026-09-18-cursor-ui-1-bienvenue.png` … `-9-overlay-repos.png` (bienvenue, PTT, masquage, local, parole, distant, overlay parole, overlay escalade, overlay repos) et `nights/2026-09-19-c2-avant.png` / `-pendant.png` / `-apres.png` pour l'alerte. **À relire avant insertion** : aucun jeton, aucun chemin personnel, aucun contenu de conversation sensible.

**8.2 Profils, parcours, standards UX/UI, accessibilité** — 5 à 8 lignes
> **Profil 1 — utilisateur mains libres** (technicien en train de travailler, yeux sur son poste) : il maintient la touche de parole, pose sa question, relâche ; la transcription s'affiche pendant qu'il parle, la réponse est dite et écrite ; s'il demande une délégation, l'état « appel distant » s'affiche et le local continue de répondre pendant l'attente. Aucune souris, aucun menu.
> **Profil 2 — utilisateur qui installe et configure** (première prise en main) : assistant en trois étapes — bienvenue, choix de la touche de parole, masquage de la fenêtre — puis configuration stockée localement ; parcours entièrement réalisable au clavier.
> **Standards UX/UI** : état permanent visible (au repos / j'écoute / je réponds / appel distant / dégradé), retour dans les deux canaux à chaque action, pas de mode caché, latence annoncée plutôt que silence.
> **Principes d'accessibilité retenus (au moins 2)** : (1) **alternative textuelle à la voix** — transcription et réponse toujours affichées, donc utilisable par une personne malentendante ou en environnement bruyant ; (2) **navigation clavier intégrale** — Tab parcourt les commandes, Entrée active, la touche de parole peut être maintenue (compatible switch/toucher lent) ; (3) **contrastes** — bandeau d'alerte `#7a1212` sur `#fff8e8`, ratio ≥ 4,5 (WCAG AA).

### SECTION 9 — Configurer les flux de données

**9.1 Trois flux** — *À la soutenance, exécuter le flux A de bout en bout.*

| Flux | Source → Cible | Règles appliquées | Format et transfert | Confidentialité |
|---|---|---|---|---|
| **A — voix → réponse vocale locale** | Micro → EARS (Whisper large-v3) → BRAIN (Granite 4.2 3B `:8090`) → MOUTH (Magpie Sofia `:8092`) → haut-parleur + écran | Transcription avant tour de décision ; tri : nombres convertis en lettres avant synthèse (les chiffres arabes étaient perdus par Magpie) ; contrôle : identité et règles vocales injectées par prompt système ; mise à jour : aucun état conservé entre séances | Trames audio WebSocket, JSON interne, WAV PCM16 22050 Hz en sortie | **Voie nominale entièrement locale** : rien ne sort du poste. Audio non conservé `[P]` |
| **B — escalade distante contrôlée** | Utilisateur → GATE → pont agent `:8765`/`:8766`/`:8767` → réponse restituée en texte et voix | Déclenchement **uniquement** sur demande explicite ; contrôle d'autorisation par `GATE_MODE` ; classification de l'outil `danger="read"` ; annonce visuelle de l'appel distant ; repli local si le pont est indisponible | `POST /ask`, JSON, jeton Bearer lu depuis `.env.local` | Sortie de données **visible par l'utilisateur** et minimisée ; la catégorie `read` n'autorise pas à dissimuler la sortie |
| **C — santé → note de coffre** | Camunda (départ nocturne) → worker `health-check` → worker `vault-note` → coffre Obsidian | Orchestration BPMN, 3 tentatives par tâche ; statuts `UP` / `DEGRADED` ; contrôle : **écriture puis relecture** du fichier avant complétion du job ; mise à jour : note datée `YYYY-MM-DD-HEALTH.md` | REST v2 JSON côté Camunda, Markdown côté coffre | Aucun secret dans la note ; droits du coffre à formaliser `[P]` |

**9.2 Justifications et contrôle qualité** — 3 à 5 lignes
> Formats choisis pour la performance et la confidentialité : l'audio reste en trames WebSocket non persistées plutôt que d'être écrit sur disque ; la réponse vocale est en WAV PCM16 à 22050 Hz, échantillonnage suffisant pour de la parole et trois fois plus léger que du 44,1 kHz ; les échanges de contrôle sont en JSON, verbeux mais lisible dans un OUT et vérifiable à la sonde. Les contrôles qualité sont intégrés aux workflows et non ajoutés après : dans le flux C, la **relecture du fichier** avant complétion du job est le contrôle — le worker ne peut pas déclarer écrite une note absente ; dans le flux B, la **porte GATE** décide avant l'appel et le journal d'audit ne conserve que des paramètres assainis ; dans le flux A, le **registre d'outils** refuse un outil non prévu au démarrage.

### SECTION 10 — Intégrer alertes et gestion des erreurs

**10.1 Mécanisme d'alerte et scénario de reprise** — 4 à 8 lignes, **captures à joindre**

> **Mécanisme d'alerte.** *Déclencheur* : cinq sondes de santé interrogées en boucle toutes les **2 secondes** par Presence — Camunda `:8088`, pont Codex `:8765`, pont Claude `:8766`, accueil host-agent `:8001`, modèle local `:8090`. Un service qui ne répond pas dans le délai de 1,5 s fait basculer l'état de `UP` à `DEGRADED`. *Canal* : bandeau d'alerte dans Presence, contraste WCAG ≥ 4,5 (`#7a1212` sur `#fff8e8`), plus une note écrite dans le coffre. *Destinataires* : l'utilisateur présent (bandeau) et l'équipe (note datée). L'annonce vocale de l'alerte est en P0 roadmap : elle n'est pas encore branchée.
> **Scénario de reprise.** Trois temps : (1) **constater** — le bandeau nomme le service dégradé et l'interface continue de fonctionner en local, donc la présentation ne s'arrête pas ; (2) **relancer** — une relance unique par script de reprise, conformément à la procédure SKU10, au lieu d'une suite de réparations improvisées ; (3) **vérifier** — le retour à `UP` est constaté par la sonde, pas supposé. Mesures réelles de la démonstration C2 (coupe simulée du pont Codex vers `127.0.0.1:1`) : `UP` en **41 ms** → `DEGRADED` en **1560 ms** → retour `UP` en **52 ms**. 7 tests verts, trois captures datées (avant / pendant / après).
> **Lien avec les risques de la section 3.** Ce mécanisme clôture deux risques du tableau : « défaillance d'un service tiers » (repli local + alerte visible + note) et « note de santé erronée » (relecture avant complétion). Il rend également visible le risque « exfiltration via appel distant », puisque l'état d'appel distant est affiché en permanence.

**10.2 Messages d'erreur** — reprendre mot pour mot les messages réels de l'OUT C2
> Trois exemples, tels qu'affichés (à recopier depuis `nights/2026-09-19-C2-ALERTE.md`, messages FR exacts) :
> 1. **Service tiers dégradé** — bandeau nommant le service et la conduite à tenir ; clair (quoi), contextualisé (quel service), non culpabilisant, et doublé d'une alternative texte donc lisible par une personne malentendante ou malvoyante grâce au contraste ≥ 4,5.
> 2. **« Canal pas encore prêt. »** — affiché quand l'utilisateur appuie sur la touche de parole avant l'ouverture du WebSocket (correctif C10) : dit ce qui se passe sans jargon technique, et évite l'appui qui tombe dans le vide sans explication.
> 3. **Réponse locale en cas de pont indisponible** — l'outil annonce l'indisponibilité et poursuit localement au lieu de produire une erreur brute ou un silence.
> Principe commun : jamais de trace technique ni de code d'erreur brut à l'utilisateur ; toujours l'état + la conduite à tenir ; toujours le doublon texte/voix.

### SECTION 11 — Intégrer des services tiers, API et IA

**11.1 Services tiers** — 5 à 9 lignes, captures bienvenues

> **Services intégrés.** (1) **Agents IA distants** via trois ponts HTTP locaux : Codex `:8765`, Claude `:8766`, Qwen `:8767` — rôle : traiter une tâche que le cerveau local de 3 milliards de paramètres ne peut pas mener (analyse de code volumineuse, recherche approfondie). (2) **Recherche web** : SearXNG en local d'abord, puis chaîne de replis DuckDuckGo → Tavily → Brave → Exa → Jina → Serper. (3) **Camunda 8** `:8088` pour l'orchestration BPMN. (4) **Intégrations optionnelles à clé facultative** : JeV pour l'entrée mains libres, StepAudio TTS pour une voix distante.
> **Paramétrage.** Chaque service est inscrit au registre d'outils **seulement si sa configuration est présente** : sans jeton, l'outil n'existe pas, il n'échoue pas en pleine conversation. Le cerveau local expose un contrat compatible OpenAI, la voix un contrat OpenAI-compatible en WAV PCM16 : un fournisseur peut être remplacé sans réécrire le host-agent.
> **Authentification et gestion des secrets.** Jeton **Bearer** par pont, lu exclusivement depuis l'environnement ; fichier `.env.local` hors versionnage, monté en lecture seule dans le conteneur ; refus 401 prouvé par sonde sans jeton ; journal d'audit conçu pour ne conserver que des paramètres assainis (ADR-012). **Action à faire avant lundi** : les clés affichées en séance le 19/09 (JeV, Step, Hugging Face) sont marquées à régénérer — ne jamais laisser une clé réelle visible dans une capture du dossier.
> **Justification au regard des contraintes.** Le distant est un complément, jamais le chemin par défaut : la contrainte RGPD impose que la voix et sa transcription restent sur le poste, la contrainte de coût impose zéro abonnement par requête, et la contrainte de démonstration impose qu'une panne tierce ne coupe pas la présentation. D'où l'architecture local-first avec escalade à la demande, et le choix de Camunda plutôt que d'un script : le flux reste modifiable sans redéploiement.

**11.2 Vérifications et impacts** — 3 à 5 lignes
> *Vérifications techniques* : sondes de disponibilité avec PONG relevé le 19/09 sur `:8765` et `:8766` ; tests de registre avec et sans jeton (37 tests C1, 133 tests de régression outils) ; chaîne de repli web couverte par 74 tests — **sur doubles, aucun réseau réel appelé**, donc la validation en conditions réelles reste à faire. *Sécurité* : refus 401 sans jeton, secrets hors git, moindre privilège par classification `danger="read"`. *Performance* : délai de sonde 1,5 s, boucle de 2 s, temps de réponse mesurés (41 ms `UP`, 52 ms retour). *Impacts environnementaux* : aucun appel distant à chaque tour — la décision vient de l'utilisateur, ce qui borne mécaniquement la consommation ; modèles quantifiés sur un seul GPU grand public (7,3 Go/12) plutôt qu'une API par requête ; l'outil de calcul local évite un aller-retour réseau pour une opération arithmétique. *Impacts éthiques* : la sortie de données est rendue visible à l'écran, le contenu externe est traité comme non fiable (injection de prompt), et aucune délégation autonome — l'utilisateur reste décideur.

---

## C. Soutenance — 15 min + 10 min

### C1. Déroulé chronométré (ÉTAPE 1 du guide)

| Temps | Séquence | Ce que le jury voit et entend |
|---|---|---|
| 0:00–1:30 | Contexte et cahier des charges | « Une équipe tech pilote plusieurs agents IA et perd du contexte entre les fenêtres. Contraintes éliminatoires : français, Windows, un GPU 12 Go, aucune voix dans le cloud. J'ai tenu le produit et la recette ; la réalisation est déléguée à des agents IA sous circuit de responsabilité outillé. » |
| 1:30–3:30 | Architecture et interopérabilité | Schéma C4 niveau 1. Trois choix à justifier, pas plus : (1) **local-first avec escalade à la demande** — RGPD, latence, coût ; (2) **chaque brique est un service sur son port** — EARS/BRAIN/MOUTH interchangeables, trois modèles d'oreille testés en une journée ; (3) **Camunda BPMN** pour que le flux santé→note soit lisible par un non-développeur : c'est la partie low code. |
| 3:30–11:30 | **Démonstration en direct** | Le fil unique ci-dessous (C2) |
| 11:30–13:30 | Sécurité, tests, qualité | Trois chiffres, pas trente : **1105 tests passés** ; **VRAM 7,3 Go/12** ; **premier son ~1,1 s**. Puis : « la carte des modèles n'a pas été choisie sur catalogue mais à l'aveugle par l'utilisateur final, à volume égalisé » — c'est la meilleure preuve que les choix sont les vôtres. |
| 13:30–15:00 | Évolutions et conclusion | P0 = prouver C1 en live et brancher l'annonce vocale de l'alerte. P1 = recherche web en conditions réelles, première requête perdue, mots imposés Whisper. P2 = Hyper-Ambiant-XL. Conclusion : « le recadrage du 19 a supprimé le routeur d'escalade autonome — l'utilisateur décide du distant, c'est un choix produit, pas une limite technique. » |

### C2. Scénario de démonstration enchaîné (ÉTAPE 2) — **un seul fil**

> PRÊT À COLLER dans le tableau du guide.

| Étape | Ce que je montre à l'écran | Ce que je dis | Durée |
|---|---|---|---|
| **Parcours profil 1** (utilisateur mains libres) | Presence au repos, alternative texte visible. J'appuie sur la touche de parole, je pose une question métier, je relâche. La transcription s'écrit, la réponse est dite **et** affichée. | « Profil 1 : aucune souris. La voix entre, la voix sort, et le texte reste affiché en permanence — c'est l'alternative d'accessibilité. Tout se passe sur le poste : 0,45 à 0,7 seconde pour la transcription, 25 à 70 millisecondes pour le premier jeton, environ 1,1 seconde avant le premier son. » | 2:00 |
| **Parcours profil 2** (première installation) | Assistant d'onboarding : bienvenue → touche de parole → masquage. Configuration écrite localement. | « Profil 2 : quelqu'un qui installe. Trois étapes, tout au clavier, configuration stockée en local. » *(si le parcours live est risqué : montrer les 3 captures datées)* | 1:00 |
| **Flux de bout en bout** | Je demande une opération qui passe par l'outil `calculer`, puis une question qui montre l'identité produit. | « Flux A exécuté de bout en bout : micro → EARS → BRAIN → MOUTH → écran et haut-parleur. Le modèle local se trompe en calcul mental, donc j'ai ajouté un outil de calcul déterministe en local : 30 tests, aucun appel réseau. C'est un choix de sobriété autant que de fiabilité. » | 2:00 |
| **Alerte + reprise** *(obligatoire)* | **Je coupe le pont Codex** (URL vers `127.0.0.1:1`). Le bandeau d'alerte apparaît en ~1,5 s, nomme le service. Je montre les états avant / pendant / après. Je relance par le script de reprise. Le bandeau repasse au vert. | « Cinq sondes toutes les deux secondes, délai de 1,5 seconde. Le service tombe : l'état passe de UP à DEGRADED, le bandeau s'affiche avec un contraste supérieur à 4,5 — WCAG AA — et l'application continue de fonctionner en local, donc la présentation ne s'arrête pas. Reprise : une seule relance par script, comme écrit dans ma procédure d'incident, pas de bricolage en direct. Retour UP constaté par la sonde en 52 millisecondes. Une note est écrite dans le coffre, et le worker la relit avant de finir son job. » | 2:30 |
| **Service tiers** *(obligatoire)* | Je demande explicitement une délégation à Claude via le pont `:8766`. L'état « appel distant » s'affiche. La réponse revient en texte et en voix. Puis je montre le registre d'outils au démarrage : `OUTILS: ask_claude, ask_codex, web_search`. | « Le distant n'est appelé que si je le demande, derrière une porte d'autorisation, avec un jeton Bearer lu depuis un fichier hors versionnage. Sans jeton, l'outil n'existe pas au démarrage — il n'échoue pas en pleine conversation, et la sonde sans jeton renvoie 401. La sortie de données est affichée à l'écran : l'utilisateur voit toujours ce qui quitte le poste. » | 2:30 |

**Plan B par étape** (à écrire, le guide le demande explicitement) :
- *Profil 1 muet* → captures `nights/2026-09-18-cursor-ui-5-parole.png` + `-6-distant.png`, et je commente les mesures du test live du 19/09.
- *Onboarding qui ne part pas* → les 3 captures datées du parcours (bienvenue, PTT, masquage).
- *Première requête perdue* (bug connu, non résolu) → je le dis et je répète la phrase : « c'est un défaut connu, la lane C10 a livré un correctif partiel, la piste restante est le lancement en pythonw ». L'honnêteté marque des points, l'improvisation non.
- *Alerte qui ne se déclenche pas* → captures `2026-09-19-c2-avant/pendant/apres.png` + les mesures de l'OUT C2 (41 ms / 1560 ms / 52 ms).
- *Pont tiers injoignable* → c'est précisément le scénario d'alerte : je bascule dessus et je montre le repli local.
- *GPU saturé* → ne charger **aucun** modèle hors profil ; procédure SKU10 : contrôles, puis une relance unique, puis escalade.

### C3. Les 8 questions du jury — réponse d'**une phrase** chacune

> PRÊT À COLLER (ÉTAPE 3 du guide).

1. **Pourquoi cette plateforme plutôt qu'une autre ?** → Camunda 8 parce que le flux doit rester modifiable par un non-développeur et que son modeleur BPMN porte déjà les reprises (3 tentatives par tâche) ; et MOTHER en code parce qu'aucune plateforme no code du marché ne tient un assistant vocal français sur un GPU 12 Go sans envoyer l'audio dans le cloud.
2. **Si vous étiez en groupe, qu'avez-vous fait vous-même ?** → Projet individuel : j'ai tenu le périmètre, les arbitrages et la recette, et j'ai délégué la réalisation à des agents IA sous circuit de responsabilité outillé où chaque tâche produit un artefact de sortie et un code de retour.
3. **Que se passe-t-il si le service tiers tombe en panne ?** → Cinq sondes le détectent en moins de deux secondes, un bandeau le dit, l'application bascule sur le local, et une relance unique par script la ramène au vert — c'est exactement la démonstration que je viens de faire.
4. **Comment votre solution respecte-t-elle le RGPD ?** → La voix et sa transcription sont traitées et non conservées sur le poste, les secrets sont hors versionnage, la sortie vers un tiers n'a lieu qu'à la demande explicite de l'utilisateur et est affichée à l'écran — et je dis au jury que la base légale, la notice et la procédure d'effacement restent à formaliser avant un usage réel.
5. **Comment un utilisateur en situation de handicap utilise-t-il vos interfaces ?** → Soit tout à la voix, soit tout au clavier avec le texte affiché en permanence : Tab parcourt, Entrée active, la touche de parole peut être maintenue, et le bandeau d'alerte dépasse 4,5 de contraste.
6. **Que disent vos tests de performance et d'accessibilité ?** → Performance : environ 1,1 seconde avant le premier son, 7,3 Go de VRAM sur 12, 1105 tests passés ; accessibilité : le contraste et la navigation clavier sont vérifiés, la validation en situation avec un lecteur d'écran reste à faire et je le dis plutôt que de la prétendre.
7. **Comment déployez-vous une évolution sans couper le service ?** → Branches avec suites de tests avant fusion, bascules par configuration pour tout ce qui est risqué, et retour arrière au commit précédent — le local-first garantit qu'un composant distant en panne ne coupe pas la voix.
8. **Que feriez-vous avec un mois de plus ?** → Prouver le tour vocal complet vers un pont externe en conditions réelles, brancher l'annonce vocale de l'alerte, valider la chaîne de recherche web sur réseau réel, et résoudre la première requête perdue.

### C4. Checklist la veille (ÉTAPE 4 du guide)

- ☐ Scénario chronométré **deux fois**, bouclé sous 14 minutes (si dépassement : couper dans la présentation, **jamais** dans les deux démonstrations obligatoires).
- ☐ **Relancer les suites de tests** sur le poste du jour J et coller la sortie dans un OUT daté — les 1105 passés datent du 19/09, une mesure historique ne remplace pas une exécution récente.
- ☐ Contrôles SKU10 sur le poste réel : conteneur démarré, santé `:8090`, santé `:8001`, Presence visible, VRAM ≤ 10 Go.
- ☐ Jetons présents dans `.env.local`, **clés du 19/09 régénérées**, aucun secret visible dans aucune capture du dossier.
- ☐ Captures de secours exportées et ouvertes une fois : ui-1 à ui-9 + c2-avant/pendant/après.
- ☐ Vérifier le réseau du lieu (les ponts sont locaux, mais Camunda et les replis web ne le sont pas tous).
- ☐ Dossier enregistré en `.docx` ou exporté en `.pdf` et **déposé avant la date limite de la convocation**.

---

## D. Trous `[À PROUVER]` restants et reformulations « cible »

L'annexe technique comptait 24 `[À PROUVER]`, ramenés à ~20 le 20/09 à 10h39. Voici ceux qui **bloquent une case du dossier**, avec la formulation qui dit vrai sans prétendre.

| # | Trou restant | Cases concernées | Reformulation « cible » à écrire | Comment le prouver lundi (coût) |
|---|---|---|---|---|
| **D-0** | **Écart no code/low code** : le jury attend Make/n8n/Bubble, MOTHER est du code | En-tête, §1.2, question 1 | « Camunda 8 porte l'orchestration en BPMN modélisable ; le composant IA local est développé parce que les contraintes — français, Windows, 12 Go de VRAM, aucune voix dans le cloud — ne sont couvertes par aucune plateforme no code du marché. » | Rien à prouver : c'est un arbitrage à **assumer en une phrase**, pas à justifier pendant 3 minutes |
| **D-1** | **C1 — tour vocal complet vers un pont externe** : registre et clés prouvés (37 tests), la boucle voix→outil→pont→voix ne l'est pas | §2.1, §4.1 T2, §11.1, **démo obligatoire « service tiers »** | « Le registre d'outils et l'authentification Bearer sont prouvés par 37 tests et par sonde (401 sans jeton, 200 avec) ; la démonstration en direct montre la délégation demandée par l'utilisateur vers le pont Claude. » | **Le plus coûteux et le plus nécessaire.** Un seul run live filmé + log `OUTILS:` au boot réel + OUT daté. À faire en priorité absolue |
| **D-2** | **Ponts en localhost uniquement** : convention de code, pas de mesure | §3.1, §3.2 | « Les services écoutent sur la machine et le code avertit de ne pas les exposer ; la vérification par mesure réseau est prévue au plan de clôture. » | Très faible coût : une capture `netstat -ano` filtrée sur 8001/8090/8765/8766/8767 suffit à transformer le `[P]` en preuve |
| **D-3** | **Audio non conservé** | §3.1, §5.2, question RGPD | « Aucun audio n'est persisté dans la voie nominale : les trames circulent en WebSocket et la réponse est synthétisée à la volée ; la politique de conservation reste à formaliser. » | Faible coût : vérifier l'absence d'écriture de fichier audio + citer la ligne de code, ou assumer la seconde partie de la phrase |
| **D-4** | **Exécution Camunda de bout en bout à la soutenance** | §2.2, §9.1 flux C, §5.1 | « Le processus BPMN et le worker sont livrés et testés, avec relecture du fichier avant complétion du job ; le déploiement et la planification en direct restent à rejouer. » | Moyen coût : un déploiement + une exécution horodatée + la note Markdown produite |
| **D-5** | **Retours utilisateurs automatisés (bouton feedback → issue GitHub, lecture 1×/jour)** | §5.3 | **Ne pas l'écrire.** Utiliser les deux canaux réels : les lanes du circuit de responsabilité (écart → lane → OUT horodaté) et le protocole de dégustation à l'aveugle du 19/09 | Aucun : remplacer par du vrai plutôt que prouver du faux |
| **D-6** | **Accessibilité en situation** (lecteur d'écran, parcours clavier intégral mesuré) | §4.1 T6, §5.2, §7.1, question handicap | « Le contraste du bandeau d'alerte est mesuré à plus de 4,5 (WCAG AA), la navigation clavier et l'alternative texte sont conçues dans Presence ; la validation en situation avec un utilisateur et un lecteur d'écran est au plan. » | Faible coût si on se limite au clavier : un parcours Tab/Entrée filmé. Ne **pas** promettre le lecteur d'écran |
| **D-7** | **Première requête perdue** — correctif C10 livré, bug encore intermittent | §4.2, plan B démo | « Un défaut intermittent subsiste en début de séance ; le correctif livré réduit le cas (appui avant ouverture du WebSocket), la piste restante est le mode de lancement de l'application. » | Ne pas le cacher : le **dire** est plus solide. Le résoudre coûte cher à J-1, le déclarer coûte zéro |
| **D-8** | **Recherche web en conditions réelles** — 74 tests sur doubles, aucun réseau réel ; symptôme « rien trouvé » ouvert | §11.1, §11.2, §2.1 SearXNG | « La chaîne de repli multi-fournisseurs est livrée et couverte par 74 tests sur doubles ; la validation sur réseau réel est en cours, l'instance locale rendant actuellement zéro résultat à cause de CAPTCHA moteurs. » | Moyen coût, et **risqué** : ne pas en faire un élément de démo |
| **D-9** | **C2 — annonce vocale de l'alerte non branchée** (affichage seulement) | §10.1, §8.2 mains libres | « L'alerte est visuelle et écrite dans le coffre ; son annonce vocale est en P0 de la feuille de route. » | Faible coût mais dépend d'un arbitrage (pas de point d'entrée sur le host-agent) — **ne pas tenter à J-1**, le déclarer |
| **D-10** | **Modules livrés non branchés** : JeV réflexe (C3, médiane 325 ms) et StepAudio TTS distant (C5) | §11.1 | Les citer comme **intégrations optionnelles à clé facultative**, jamais comme faisant partie du parcours démontré | Rien à prouver : la carte figée les classe déjà ainsi |
| **D-11** | **EN 0.1 — pas de preuve de tour vocal live complet en anglais** | En-tête périmètre, §6.1 | « Le support anglais est livré en 0.1 et couvert par 13 tests plus les régressions françaises (14 et 2), avec bascule par variable d'environnement et français par défaut ; la locale n'est pas encore persistée dans la configuration. » | Faible coût : un tour vocal live en anglais filmé. Mais **ne pas** l'annoncer dans la démo sans l'avoir répété |
| **D-12** | **Chiffres RICE non chiffrés** | §6.1 | Garder la priorisation **qualitative** avec la source de décision en dernière colonne, comme dans l'annexe | Aucun : ne pas inventer de reach/impact/confidence/effort chiffrés |
| **D-13** | **Journal de versions incomplet** (dates et auteurs à tirer de `git log`) | §7.2 | — | Très faible coût : `git log --pretty=format:"%h|%ad|%s|%an" --date=short -25` |
| **D-14** | **Droits du coffre et rétention des notes non formalisés** | §2.1, §3.1 | « Les notes sont en Markdown dans un coffre local ; la politique de rétention et les droits d'accès restent à formaliser. » | Aucun à J-1 : le déclarer suffit |
| **D-15** | **Revue des captures avant publication** (secrets, chemins personnels, contenu de conversation) | §8.1, annexe B | — | **Obligatoire et bloquant** : relire chaque capture insérée. Une clé visible dans le dossier annule l'argument RGPD |

**Ordre de traitement proposé pour ce qui reste de la journée** : D-15 (bloquant, 15 min) → D-1 (démo obligatoire) → D-13 (2 min) → D-2 (5 min) → D-6 clavier seul (10 min). Le reste se traite par la reformulation « cible », qui est déjà rédigée ci-dessus.

---

## E. Esprit produit — le fil à tenir dans tout le dossier

Ce ne sont pas des arguments ajoutés : ce sont les cinq intentions qui expliquent **pourquoi** chaque choix technique a été fait. À glisser en une phrase dans les sections indiquées, et à garder en bouche pour les questions du jury.

**1. Automation — automatiser ce qui doit l'être, jamais ce qui engage.** Trois niveaux assumés et écrits dans l'annexe §5 : *automatisé* (santé nocturne → note), *semi-automatisé* (veille de nuit avec validation humaine), *déclenché par l'utilisateur* (consultation d'un agent, recherche web). Le critère de bascule n'est pas technique mais de responsabilité : dès qu'une action sort du poste, la décision revient à l'humain. C'est pourquoi le **routeur d'escalade autonome a été supprimé du produit** le 19/09 (recadrage JeV) alors qu'il était techniquement faisable. *Où l'écrire : §1.2, §5.1, §11.2, question 3.*

**2. Orchestre — une flotte d'agents avec un seul chef d'orchestre.** Le produit est double : il orchestre des briques techniques (EARS → BRAIN → MOUTH, GATE, ponts, Camunda) **et** il orchestre une flotte d'agents IA qui le construisent (Cursor au code, Codex en overflow et documentaire, Claude au lead technique et à l'arbitrage, Qwen sur le dossier, OC à l'horloge et comme pont unique vers les harnais, OG au kanban). Le point produit est là : une flotte sans circuit de clôture produit des lanes fantômes. D'où `account.py` — états start/doing/done/fail, artefact OUT obligatoire, code EXIT, notification (simple → OC et ponts ; complexe → OG qui informe OC), et la règle « open sans close = fuite ». Le circuit a été validé par trois tests fumée le 20/09, tous EXIT 0. *Où l'écrire : rôle et contributions personnelles, §5.1, §7.1, question 2 — c'est le meilleur making-of disponible.*

**3. Accessibilité mains libres — la voix est un canal, pas une contrainte.** Deux principes : l'usage 100 % voix est possible **et** l'alternative texte est permanente, donc personne n'est exclu par le choix du canal. Concrètement : transcription affichée pendant la parole, réponse écrite et dite, état d'appel distant visible, navigation Tab/Entrée, touche de parole maintenable (compatible switch et toucher lent), bandeau d'alerte à contraste ≥ 4,5. Corollaire produit : **une alerte uniquement visuelle est incomplète pour un produit mains libres** — c'est exactement pourquoi l'annonce vocale de l'alerte est en P0 (D-9), et le dire au jury montre qu'on a compris son propre produit. *Où l'écrire : §5.2, §8.2, §10.2, questions 5 et 6.*

**4. Feedback — la boucle courte comme mécanisme de qualité.** Trois boucles de tailles différentes : la boucle **seconde** (sonde toutes les 2 s, délai 1,5 s → l'utilisateur sait immédiatement que ça tombe) ; la boucle **jour** (BPMN nocturne → note de santé relue avant complétion, donc pas de faux « écrit ») ; la boucle **tâche** (lane ouverte → OUT → EXIT → notification). S'y ajoute la boucle **humaine** qui a tranché le plus important : le protocole de dégustation du 19/09, où l'utilisateur final note **à l'aveugle**, à volume égalisé pour les voix, sur questions improvisées pour les cerveaux et sur ses propres enregistrements pour l'oreille. Résultat produit : Granite 4.2 3B retenu à 4,57/5 devant un modèle mieux noté mais deux fois plus gourmand en VRAM. C'est la preuve la plus forte que les choix appartiennent au candidat. *Où l'écrire : §4.2, §5.1, §5.3, §7.2, question 6.*

**5. Modularité — chaque brique est remplaçable, donc le produit peut vieillir.** EARS, BRAIN et MOUTH sont trois services distincts derrière des contrats stables (compatible OpenAI pour le cerveau, WAV PCM16 pour la voix), plus GATE pour l'autorisation et un registre d'outils conditionné à la configuration. Ce n'est pas une vue de l'esprit, c'est mesuré : trois modèles d'oreille bancs-testés en une journée (Whisper large-v3, Parakeet, Canary) sans toucher au host-agent ; voix passée de 4473,2 ms à 1341,1 ms de TTFA en changeant de backend et de device ; un outil `calculer` ajouté en local pour compenser une faiblesse du cerveau sans changer de cerveau ; trois fournisseurs de recherche branchés en chaîne de repli sans réécrire l'appelant. Corollaire : chaque modèle retenu a un **repli documenté** (NeoHorse-1-9B puis Ministral-3-8B pour le cerveau, Parakeet-TDT-0.6B-v3 pour l'oreille, Supertonic F5 sur CPU à 0 VRAM pour la voix) — c'est ce qui rend la continuité de service du §6 crédible. *Où l'écrire : §1.2, §2.2, §6.1, §6.2, question 7.*

### La phrase de fermeture à préparer (fin de soutenance)
> « Ce que je retiens de ce projet : la contrainte la plus forte n'était pas technique mais de confiance — un produit qui parle doit faire entendre ce qu'il fait. D'où le local par défaut, l'état distant affiché en permanence, l'alerte qui nomme le service, et un circuit de responsabilité outillé pour les agents qui le construisent. Tout le reste en découle. »

---

## F. Rappel de fin de lane

- Ce fichier est une **aide**, pas le dossier : Thomas écrit les cases.
- Lane `BGB-AIDE` ouverte dans `ACCOUNTABILITY-BOARD.md`, complexité **simple** → notification OC + ponts.
- Clôture : `python dev/scripts/account.py close --lane BGB-AIDE --status done`
- Aucune donnée sensible dans ce fichier. Les clés affichées en séance le 19/09 restent **à régénérer** avant tout dépôt public.
