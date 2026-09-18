---
date: 2026-09-17
heure: ~19:30 Europe/Paris
type: out
auteur: Muse (harnais)
cible: Thomas + Claude lead + OC
statut: livré — cadrage seul, live intact, réponses Thomas 19:21 intégrées
related:
  - "[[2026-09-17-BRIEF-MUSE-HARNAIS]]"
  - "[[2026-09-17-QUESTIONS-HARNAIS]]"
  - "[[2026-09-17-PLAN-SOIR]]"
  - "[[2026-09-17-KANBAN]]"
  - "[[2026-09-15-MUSE-OUTILS-PONTS]]"
---

# Harnais voix → Codex / Claude / Hermes + onboarding LLM (17 sept)

Règle tenue : **rien touché** au live (ni voix/TTS/hostagent, ni `.env.local`,
ni conteneur, ni SAWB/Hermes2). Probes = lecture seule depuis ce sandbox
(qui ne voit ni host Windows ni Docker : `000` attendu, comme le 15 sept).

## 1. Options harnais (voix → outil externe)

| # | Option | Principe | + | − |
|---|---|---|---|---|
| A | **Pont HTTP local headless** (existant : 8765/8766) | La voix appelle `POST /ask` sur pont Windows qui lance le CLI (`codex`, `claude`) et rend le texte | Déjà codé + testé (137 passed le 15) ; silencieux, rapide, scriptable ; token dédié par pont | Exige CLI auth + pont allumé + `.env.local` + relance routeur |
| B | **MCP** (serveur MCP MOTHER exposé aux agents) | Codex/Claude/Hermes appellent MOTHER comme outil (sens inverse : l'agent pilote) | Standard, traçable, bon pour démo « outil externe » soutenance | Sens inverse du besoin voix (« envoie à X ») ; dev neuf, pas pour 20:15 |
| C | **API distante directe** (HTTP vers gateway Hermes / API cloud) | Voix → HTTP direct sans CLI local | Simple si gateway déjà Up (cas Hermes) | Secrets exposés, dépend réseau, hors contrôle local ; SAWB à protéger |
| D | **Ouvrir UI + coller prompt** | La voix ouvre une fenêtre (terminal / app) avec le prompt pré-rempli, Thomas valide | Visible en démo, zéro auth machine, secours universel | Pas headless, pas automatisable, lent |

Sens des options : A et D partent de la voix vers l'outil (le besoin).
B part de l'outil vers MOTHER (complément, pas substitut). C est une
variante de A sans CLI, réservée à Hermes-gateway.

## 2. Recommandation pour le créneau 20:15

**A par défaut (Codex + Claude headless), D en secours visible, C pour
Hermes en appel only, B reporté après-soutenance.**

- Q4 → **(C) les deux selon outil** : headless (A) quand le pont
  répond, sinon ouverture UI (D) avec prompt pré-rempli.
  Jamais de silence : fallback parlé si pont fermé (comportement voulu,
  pas une panne).
- Codex (Q1) : pont 8765 + `CODEX_BRIDGE_TOKEN` dédié, headless OUI.
  Interactif = ouvrir CLI seulement (D). Vérifier `codex` déjà auth
  côté Windows avant 20:15 (`codex --help` / 1 PONG).
- Claude (Q2) : pont 8766 + `CLI_BRIDGE_TOKEN`, headless OUI.
- Hermes (Q3) : headless OUI mais **appel only, aucune configuration**
  côté Hermes : on appelle la gateway déjà Up en lecture seule
  (1 `GET /health` ou équivalent), on ne configure rien, on ne lance
  pas le binaire. Le chemin CLI `hermes` reste **désarmé**
  (`CLI_BRIDGE_HERMES` absent) : le pont refuse par construction
  (testé). SAWB intact.
- Q5 : workspace toujours **MOTHER-dev** (ponts lancés depuis
  `D:\BGB Training\MOTHER-dev`, lecture seule dépôt : les ponts
  lisent, n'écrivent rien).

## 3. Réponses aux 5 questions harnais — LOCKED Thomas ~19:21

1. Codex auth + pont 8765 + token ? — **OUI headless** + interactif =
   ouvrir CLI seulement. Code prêt (`native/codexbridge/bridge.py`,
   port 8765, `POST /ask {"question"}`, Bearer `CODEX_BRIDGE_TOKEN`).
2. Claude headless 8766 + token ? — **OUI headless**. Code prêt
   (`native/clibridge/bridge.py`, port 8766,
   `POST /ask {"question","agent"}`, Bearer `CLI_BRIDGE_TOKEN`).
3. Hermes gateway, appel sans casser SAWB ? — **OUI headless, appel
   only, aucune configuration** : 1 appel lecture seule vers la
   gateway Up, rien d'autre. Reste à obtenir : URL + endpoint health
   (token seulement si la gateway l'exige).
4. Comportement live (A/B/C) ? — **C verrouillé** : headless puis UI
   selon outil, fallback parlé.
5. Workspace toujours MOTHER-dev ? — **Oui, verrouillé.**

## 4. Esquisse onboarding LLM-local intelligent — V1 papier

Objectif : ajouter un modèle distant + des harnais locaux guidés par le
cerveau local, sans bluff live (rien de promis qui ne soit prouvé).

- Étape 1 — Déclarer : l'utilisateur ajoute un modèle distant
  (nom + URL + clé, stockés en `.env.local`, jamais commit).
  Preuve : `GET /health` ou équivalent du distant → 200 affiché.
- Étape 2 — Guider : le cerveau local propose quel harnais brancher
  (Codex = fichiers, Claude = revue, distant = raisonnement)
  sous forme de checklist validée par Thomas, pas d'auto-armement.
- Étape 3 — Armer : chaque harnais passe au vert un par un
  (pont Up → token OK → 1 PONG réel). L'onboarding affiche
  l'état réel, jamais « connecté » sans PONG.
- Étape 4 — Essayer : 1 tour PTT par harnais armé, avec fallback
  parlé visible si échec.
- Garde-fous V1 : pas d'écriture dépôt par les ponts ; Hermes
  désarmé par défaut ; FR only ; tout secret en `.env.local`.

Base existante : Éclair distant + onboarding 3 étapes (15 sept Cursor).
V1 = durcir en 4 étapes avec preuves, pas de nouveau protocole.

## 5. Suite ponts (état ce soir, sans casser le live)

- Contrats relus dans le code : 8765 Codex / 8766 Claude, tokens
  obligatoires (pont fermé sans jeton), URLs en défaut dans
  `relancer_routeur.sh`. **Seules les 3 lignes `.env.local` manquent**
  (2 jetons + `MUSE_BRIDGE_URL`), inchangé depuis le 15 sept.
- Probes lecture seule : 8765 → `000`, 8766 → `000` (ponts non
  visibles de ce sandbox = attendu, pas une panne).
- Hermes : chemin CLI déclaré mais refusé sans `CLI_BRIDGE_HERMES=1`
  (lu dans `bridge.py`, lignes ~140-153) ; rien armé, SAWB intact.
- Aucun processus laissé, aucun fichier live modifié.

## 6. Blockers

1. Allumage ponts = côté Windows (`python -m native.codexbridge.bridge`
   / `native.clibridge.bridge`) — impossible depuis ce sandbox.
2. `.env.local` (3 lignes) + relance routeur = après allumage ponts,
   côté Windows, hors tests voix (ne pas relancer pendant PTT Thomas).
3. Hermes gateway : URL + endpoint health à obtenir pour l'appel only
   (token seulement si la gateway l'exige).
4. MCP (option B) : dev neuf, hors scope 20:15 et soutenance.
5. `codex` / `claude` auth côté Windows à confirmer avant 20:15 (1 PONG
   direct chacun).

## 7. Next — 5 étapes ordonnées (côté Windows, créneau 20:15)

1. PONG direct `codex` + `claude` (auth OK), puis allumer les ponts
   (2 fenêtres PowerShell depuis `D:\BGB Training\MOTHER-dev`,
   1 token hex par pont).
2. Poser les 3 lignes `.env.local` (2 jetons identiques aux ponts +
   `MUSE_BRIDGE_URL`) — jamais commit, jamais avant l'étape 1.
3. Relance ciblée `dev/scripts/relancer_routeur.sh` (hors PTT Thomas),
   contrôler `OUTILS: ask_claude, ask_codex, ask_muse, web_search`.
4. 1 tour PTT par outil (fichiers → Codex, revue → Claude,
   raisonnement → Muse, actu → web) + test secours D (ouvrir CLI
   Codex + coller) pour valider le mode interactif.
5. Hermes : 1 seul appel lecture seule vers la gateway (health),
   aucune configuration ; puis clôture du point.

## Ping OC

OUT livré (workspace, coffre read-only depuis WSL : à mirroirer) :
`nights/2026-09-17-MUSE-HARNAIS.md`. Réponses Thomas 19:21 intégrées
(headless OUI x3, Codex interactif = ouvrir CLI, Hermes appel only,
MOTHER-dev). Voix/TTS/live : non touchés. SAWB/Hermes2 : non touchés.
Stop après livraison, comme consigné.
