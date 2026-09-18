---
date: 2026-09-17
heure: soir Europe/Paris
type: out
auteur: Muse (onboarding LLM V1)
cible: Thomas + Cursor + Claude + OC
statut: livré — papier V1 → actionnable, live intact
related:
  - "[[2026-09-17-MUSE-HARNAIS]]"
  - "[[2026-09-17-CURSOR-UI-HA]]"
  - "[[2026-09-17-ORCH-NOW]]"
  - "[[2026-09-17-PROMPT-MUSE-ONBOARDING-V1]]"
---

# Onboarding LLM V1 — OUT actionnable (4 étapes à preuves)

Sources : MUSE-HARNAIS §4 (papier) + CURSOR-UI-HA (wizard 3 étapes OK, 20 tests) + ORCH-NOW (disjoint Cursor/Codex).
Règle tenue : rien touché (ni ponts Codex, ni Hermes config, ni docker, ni SAWB, ni voix/TTS/live). Fichier seul.

## 1. Les 4 étapes V1 (avec preuves affichées)

Règle d'or : **jamais « connecté » sans preuve**. Chaque étape affiche son test réel, en clair, FR only.

| # | Étape | L'utilisateur fait | Preuve affichée (obligatoire) | Si échec |
|---|---|---|---|---|
| 1 | **Déclarer** | Nom + URL + clé du modèle distant | `GET /health` (ou équivalent distant) → **200 affiché** + latence | Reste « non vérifié », secrets en `.env.local` seulement, jamais commit |
| 2 | **Guider** | Lit la checklist proposée par le cerveau local, coche | Checklist validée par Thomas : Codex = fichiers, Claude = revue, distant = raisonnement. **Pas d'auto-armement** | Rien ne s'arme seul |
| 3 | **Armer** | Allume chaque harnais un par un | Par harnais, 3 pastilles : **pont Up → token OK → 1 PONG réel**. Vert = les 3 vraies | Gris/rouge + cause en clair (« pont fermé », « token refusé », « pas de PONG ») |
| 4 | **Essayer** | 1 tour PTT par harnais armé | Réponse réelle affichée + parlée, ou **fallback parlé visible** (« pont fermé, je reste en local ») | Jamais de silence, jamais de bluff |

Probes de référence (côté Windows uniquement, pas depuis ce sandbox) :
- Distant : `curl -i <URL_DISTANT>/health` → 200.
- Codex : `POST 127.0.0.1:8765/ask {"question":"PONG"}` + Bearer `CODEX_BRIDGE_TOKEN` → texte PONG.
- Claude : `POST 127.0.0.1:8766/ask {"question":"PONG","agent":"claude"}` + Bearer `CLI_BRIDGE_TOKEN` → texte PONG.
- Hermes : **1 seul `GET <gateway>/health` en lecture seule si URL connue, 0 config**.

## 2. Déjà dans Presence wizard vs manque V1

**Déjà là (ne pas refaire) :**
- Wizard 3 étapes skippables FR (`native/presence/onboarding.py` : `ETAPES_WIZARD`, `TEXTE_BIENVENUE/PTT/MASQUAGE`), persistance `%APPDATA%/hyper-ambient/presence.json`.
- PTT (Espace / Ctrl+Espace, essai sans micro), masquage (`iconify`), a11y texte + focus.
- Éclair distant : éteint « Modèle local », allumé en `escalade` « Appel distant » (`eclair_allume`, `libelle_eclair`, `BadgeEclair` dans `native/presence/app.py`, `dessiner_eclair` dans `native/presence/overlay.py`).
- HA + 20 tests verts (`dev/tests/test_presence_onboarding.py`, `test_presence_interruption.py`).

**Manque V1 (le delta à coder) :**
- Pas d'étape « Déclarer distant » (nom/URL/clé → test health → `.env.local`).
- Pas de checklist « Guider » (proposition cerveau local, validation manuelle).
- Pas d'écran états harnais « Armer » (pastilles pont/token/PONG par harnais).
- Pas de tour « Essayer » PTT par harnais + fallback parlé visible.
- Pas de persistance `onboarding_llm` séparée (ne pas mélanger avec `onboarding_termine` PTT).

## 3. Next — 5 tâches ordonnées pour Cursor/Claude (après Codex, sans croiser)

Ordre strict. Surface : `native/presence` + tests uniquement.

1. **Modèle états LLM** (Claude, puis Cursor) — `native/presence/onboarding.py`
   - Ajouter `ETAPES_LLM = ("declarer","guider","armer","essayer")`, type `EtatHarnais` (gris/vert + cause), helpers `libelle_etat`, persistance `onboarding_llm` dans `presence.json`. Règle : vert = PONG réel.
2. **Écran Déclarer + test health** (Cursor) — `native/presence/app.py`, `native/presence/onboarding.py`
   - Form FR (nom/URL/clé) + bouton « Vérifier » → `GET /health` → affiche 200/latence. Écrit `.env.local` (jamais commit). Skippable.
3. **Écrans Guider + Armer** (Cursor, logique relue Claude) — `native/presence/app.py`
   - Guider : checklist lecture seule + cases Thomas. Armer : 3 pastilles par harnais (Codex 8765 / Claude 8766 / distant), chacune testée pour de vrai (Up/token/PONG). Hermes affiché « appel only » ou masqué si URL inconnue.
4. **Écran Essayer + fallback parlé** (Cursor) — `native/presence/app.py`, `native/presence/overlay.py`
   - 1 bouton PTT par harnais armé, réponse affichée, éclair allumé en escalade (réutiliser `BadgeEclair`). Échec = message parlé + texte, jamais silencieux.
5. **Tests + captures** (Cursor) — `dev/tests/test_presence_onboarding_llm.py`, `nights/2026-09-17-llm-*.png`
   - Tests : lock FR, Déclarer (health mock 200/KO), Armer (PONG mock, refus sans PONG), Essayer (fallback). Captures : 4 écrans + états harnais. Cible : `pytest dev/tests/test_presence_onboarding_llm.py -q` vert + `py_compile` presence.

## 4. Interdits (rappel ORCH-NOW)
- Ne pas toucher pont Codex :8765 en cours (Cursor/Thomas BF).
- Hermes : appel health only si URL connue, **0 config**, SAWB intact.
- Ni docker recreate, ni `.env.local` commit, ni auth redemandée à Thomas, ni widgets hors lot.

## Ping OC
OUT livré : `nights/2026-09-17-MUSE-ONBOARDING-LLM-V1.md` (workspace). Coffre RO depuis WSL : à mirroirer côté OC si besoin. Stop après OUT, comme consigné.
