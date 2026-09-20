---
date: 2026-09-20
heure: ~15:50 Europe/Paris
type: out
lane: FIX-STOP-MAINS-LIBRES
complexity: complex
notify: OG
cible: OG (puis OG → OC)
auteur: Cursor (Grok 4.6)
related: ["[[2026-09-20-BRIEF-CURSOR-FIX-STOP-MAINS-LIBRES]]"]
nudge: unique — re-preuve pytest, Presence non lancée, Codex non appelé
---

# OUT — FIX Stop + Mains libres réel (toggle, pas hold)

**STOP opérateur :** Presence non lancée. Pas de pythonw / Start-Process / hyper-ambient.bat / 2e instance. Codex non appelé.

**Thomas: ferme Presence et relance UNE fois via hyper-ambient.bat**

## Livré (déjà dans le repo, reconfirmé au nudge)

### A — Stop
- Bouton **Stop** à côté de Parler (`takefocus` + focus visible), i18n FR/EN.
- `session.couper` + `sortie.abort()` via `consommer_reponse`. Statut **Interrompue.** Pas d’écoute.
- **Échap** : Stop si TTS en cours ; sinon quitter.

### B — Mains libres = toggle sans hold
- ON : 1er appui **Écoute…**, relâcher ne fait rien, 2e appui **Envoi…**.
- OFF : PTT hold inchangé. JeV seulement si ON.
- VAD non livré (bonus). MVP press-to-start / press-to-send.

## Preuve (rejouée au nudge)

```
$ python -m py_compile native/presence/app.py native/presence/onboarding.py src/i18n/__init__.py

$ python -m pytest -q dev/tests/test_presence_stop_mains_libres.py \
    dev/tests/test_presence_interruption.py dev/tests/test_c8_i18n.py
23 passed in 1.41s
```

EXIT=0. Lane close.

NOTIFY=OG
ACTION: SendToAgent OG — lane FIX-STOP-MAINS-LIBRES done
