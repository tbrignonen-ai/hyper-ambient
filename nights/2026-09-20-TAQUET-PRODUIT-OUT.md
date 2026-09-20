---
date: 2026-09-20
heure: ~10:42 Europe/Paris
type: out
lane: TAQUET-PRODUIT
complexity: complex
notify: OG
cible: OG (puis OG → OC)
auteur: Cursor (Grok 4.6)
related: ["[[2026-09-19-CARTE-FIGEE]]", "[[2026-09-19-C8-EN-OUT]]", "[[2026-09-19-P0-2-CARTE-OUT]]", "[[2026-09-20-TAQUET-1H]]"]
deadline: 11:35 Europe/Paris
---

# TAQUET-PRODUIT OUT — carte + EN 0.1 + a11y + feedback + C13

Thomas : max features Hyper Ambient post-carte, **sans recreer docker**. Pas de commit. Aucune valeur de secret.

Carte figée inchangée : **Granite 4.2 3B Q4_K_M** + **Whisper large-v3** + **Magpie Sofia** CUDA. EN 0.1 = `HA_LANG=en` (UI/prompt/nombres), pas un second stack.

## 1) Carte persistante — vérifiée chargée

P0-2 déjà livré. Re-preuve dry-run (env de test, pas le process live) :

```
injectees: BRAIN_SERVICE, BRAIN_MODEL, BRAIN_MODEL_LOCAL, MODEL, EARS_BACKEND,
  EARS_MODEL, EARS_LANGUAGE, EARS_DEVICE, EARS_COMPUTE_TYPE, EARS_HOTWORDS,
  MOUTH_BACKEND, MOUTH_VOICE_NAME, MOUTH_LANGUAGE, MOUTH_DEVICE
BRAIN_SERVICE llamacpp
EARS faster-whisper large-v3 int8_float16
MOUTH magpie Sofia cuda
HOTWORDS MOTHER Codex Camunda Claude
MODEL granite-4.2-3b-Q4_K_M.gguf
secret leftover False
```

Commentaire ajouté dans `dev/scripts/carte_figee.env` : EN 0.1 via `HA_LANG`, la carte locale reste FR (`EARS_LANGUAGE` / `MOUTH_LANGUAGE`). Relance live **non faite** (même règle que P0-2 / WIRE).

## 2) EN 0.1 — trous UI / onboarding / README

C8 posait l'env seulement. Trous fermés :

| Trou C8 | Correctif |
|---|---|
| `langue` absente de `presence.json` | champ persisté ; radios FR/EN ; `HA_LANG` prime |
| « Canal prêt. Maintenez Parler… » dur | `ui.channel_ready` / `connecting` / `listening` / `no_frames` / `frames_sent` |
| README.en.md incomplet | a11y, JeV mains libres, feedback, persist langue |

## 3) Accessibilité (malvoyants + mains libres ; pas sourds)

- Contraste élevé persisté (`contraste` dans `presence.json`) : palettes orbe WCAG **1.4.11 ≥ 3:1** vs `FOND_CHAMP`.
- Éclair éteint a11y vs vitre `#102028`.
- Tab / Entrée / focus déjà là ; rappel + mains libres (JeV) dans l'onboarding et `README.en.md`.
- **Pas** un mode sourds : oreille + voix restent le canal, texte à l'écran.

## 4) Feedback ouvert

Bouton Presence **Un retour** / **Send feedback** → `https://github.com/tbrignonen-ai/hyper-ambient/issues/new` (`ouvrir_feedback`, injectable en test). Aucun secret.

## 5) C13 pythonw — cause prouvée, correctif minimal

**Cause (sondée)** : `pythonw` détaché → `stdout=None`, `stderr=None`, fd C 1/2 fermés. `print()` Python 3.13 ne lève pas (no-op). PortAudio/sounddevice parlent au stderr C → micro vide, WS ouvert, `AUDIO_RECV=0`. `python -u` (flux valides) marche. Cadre avec le constat live du 19/09.

**Correctif** : `assurer_stdio()` rattache stdout/stderr **et** `dup2` fd 1/2 sur `%LOCALAPPDATA%/hyper-ambient/presence.log` avant l'audio. `journaliser()` est le filet si un flux redevient `None`. `hyper-ambient.bat` reste `pythonw` (pas de terminal).

Pas de relance Presence live dans ce taquet (preuve unitaire + subprocess).

## TDD

**Rouge** (helpers absents) : 6 failed, 1 passed (carte déjà là). Assertion FR ensuite corrigée (`channel_ready` = « Maintenez {raccourci} », plus « Parler » en dur).

**Vert** (commandes exécutées) :

```
$ python -m pytest -q dev/tests/test_taquet_produit.py
.......                                                                  [100%]
7 passed in 0.24s

$ python -m pytest -q dev/tests/test_taquet_produit.py dev/tests/test_c8_i18n.py \
    dev/tests/test_carte_figee.py dev/tests/test_ears_hotwords.py \
    dev/tests/test_presence_sante.py
................................                                         [100%]
32 passed in 0.52s
```

`test_presence_onboarding.py` : un Tk flake Python 3.13 (`spinbox.tcl`) hors de ce correctif ; les tests Presence sans GUI passent.

## Diff résumé

| Fichier | Rôle |
|---|---|
| `dev/tests/test_taquet_produit.py` | 7 tests produit (carte, C13 stdio, i18n, feedback, a11y) |
| `native/presence/onboarding.py` | `langue`/`contraste`, `URL_FEEDBACK`, `ouvrir_feedback`, éclair a11y |
| `native/presence/app.py` | `assurer_stdio` + `journaliser`, UI langue/contraste/feedback, statuts i18n |
| `native/presence/overlay.py` | `PALETTES_CONTRASTE`, `palette_pour`, `palettes(True)` |
| `src/i18n/__init__.py` | clés canal / écoute / feedback / contraste / mains libres FR+EN |
| `README.en.md` | a11y + JeV + issues + persist langue |
| `dev/scripts/carte_figee.env` | commentaire EN 0.1 |
| `native/presence/hyper-ambient.bat` | note C13, toujours pythonw |

## Non fait (volontaire / hors 1h)

- Relance live host-agent / Presence (feu vert Claude, pas `docker compose up`)
- Commit / push
- Mode sourds (hors cadrage Thomas)
- Cron lecture issues (ops, pas in-app)

## Done

| Attendu | Statut |
|---|---|
| Carte Granite+Whisper large-v3+Magpie Sofia chargée | **oui** (dry-run + pytest) |
| EN 0.1 UI/onboarding/README | **oui** |
| a11y contraste + labels/focus + JeV documenté | **oui** |
| Bouton feedback GitHub issues | **oui** |
| C13 pythonw si cause prouvée | **oui** (`assurer_stdio`) |
| TDD rouge→vert collé | **oui** |
| Relance live / commit | **non** |

NOTIFY=OG — lane complexe, close → OG informe OC.
