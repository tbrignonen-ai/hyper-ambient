---
date: 2026-09-19
heure: ~20:15
type: passation
de: Claude (lead technique)
pour: Grok bot (organisateur) — reprise de l'orga avec Thomas
related: ["[[2026-09-19-CARTE-FIGEE]]", "[[2026-09-19-CLAUDE-NOTE-CODEX]]", "[[2026-09-19-CLAUDE-POUR-GROK]]", "[[2026-09-19-CLAUDE-PLAN-TECH]]"]
---

# Claude → Grok bot : la carte est figée, on enchaîne

**Carte figée** ([[2026-09-19-CARTE-FIGEE]]) : cerveau **Granite 4.2 3B Q4_K_M** · oreille **Whisper large-v3 int8** · voix **Magpie Sofia (CUDA)**. VRAM au repos 7,3 Go.
Test live de Thomas OK de bout en bout, **sauf la recherche web** (cause prouvée ci-dessous).

## État de la stack (à ne pas casser)
Conteneur `mother-core-dev` en marche : llama-server `:8080` (Granite, `/tmp/brain.sh`), host-agent `:8001` relancé par `/tmp/relance_hostagent.sh`
(cerveau local seul `BRAIN_SERVICE=llamacpp`, oreille large-v3, voix Magpie Sofia CUDA — **ces réglages ne sont pas encore dans `.env.local`**, voir P0-2),
serveur Magpie `nemo-speech serve`. Appli Presence lancée en `python -u native\presence\app.py` (traces dans le scratchpad Claude).

## À orchestrer — par priorité
| # | Tâche | Qui (conseil lead tech) | Détail |
|---|---|---|---|
| **P0-1** | **Copier les modèles retenus sur le SSD `E:`** (seulement eux) + SHA256 avant/après | Codex (luna, low) ou OC | 3 éléments listés dans la carte (Granite 2,24 Go ; dossier Whisper large-v3 2,9 Go ; Magpie 449 Mo + codec 79 Mo). Ne rien supprimer sur `D:`. |
| **P0-2** | **Rendre la carte persistante** : `.env.local` / script de lancement officiel (`BRAIN_SERVICE`, `MODEL`, `EARS_*`, `MOUTH_*`), au lieu du `/tmp/relance_hostagent.sh` de dégustation | Cursor | Accord Thomas requis pour toucher aux valeurs modèle de `.env.local`. Ne pas utiliser `docker compose up`. |
| **P0-3** | **C4 web multi-fournisseurs** — cause racine prouvée : SearXNG rend **0 résultat** (moteurs CAPTCHA/suspendus), le repli ne se déclenche que si SearXNG est injoignable ; pas de clé Tavily | Codex (terra, high) | Voir ajout dans [[2026-09-19-CLAUDE-NOTE-CODEX]]. Clé Tavily gratuite proposée à Thomas. |
| **P0-4** | **Répétition démo jury** : alerte + reprise (C2, couper le vrai pont `:8765`) et service tiers (C1 / JeV) sur la stack figée | Thomas + Claude | Démos obligatoires lundi. |
| P1 | Brancher dans le host-agent : **JeV** (C3, module prêt), **prompt identité** (C11, prêt), **hotwords Whisper** (MOTHER, Codex, Camunda, Claude), **outil calculer** (C12) | Cursor (branchement) / Codex (C12) | Un seul run sur `serve_hostagent.py` à la fois. |
| P1 | **C13 — Appli Presence lancée par `hyper-ambient.bat` (pythonw)** : au test du soir, l'audio ne partait pas (WS ouvert, aucun AUDIO_RECV) ; relancée en `python -u`, tout marche. Cause non prouvée. | Cursor (debug) | Traces C10 disponibles ; cause racine avant correctif. |
| P1 | **C5 voix distante**, **C6 onboarding vocal + visuel**, **C8 version EN 0.1** | Codex / Cursor | Voir [[2026-09-19-CLAUDE-POUR-GROK]]. |
| P1 | Packaging Magpie CUDA (binaire `nemo-speech` CUDA propre) + suite de **C7 natif Windows** (prototype) | Codex (sol, high) | |
| P1 | **Dossier BGB** : relire l'annexe X1, intégrer la méthode de dégustation (protocole + 41 captures `degustation-19/cerveau/captures/`) | Claude relit, Codex rédige | Deadline lundi. |

## Règles inchangées
Fichiers disjoints par lane · TDD · cause racine avant correctif · aucun secret affiché · pas de recreate · pas de commit sans Thomas ·
escalade vers un harnais toujours décidée par l'utilisateur. Claude reste lead technique et interlocuteur des tests live.
