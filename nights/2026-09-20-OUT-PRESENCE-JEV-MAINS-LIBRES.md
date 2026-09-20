---
date: 2026-09-20
heure: ~15:33 Europe/Paris
type: out
lane: JEV-UI + ONBOARDING-AFFINE
complexity: complex
notify: OG
cible: OG (puis OG → OC)
auteur: Cursor (Grok 4.6)
chat: 62c1592a-9125-4481-8cf7-ce6e95d0b1ee
related: ["[[2026-09-20-BRIEF-CURSOR-PRESENCE-JEV]]"]
---

# OUT — Presence Mains libres (JeV) + onboarding

**STOP opérateur :** aucune Presence lancée à la clôture. Thomas garde **son** instance. Il testera lui-même. Pas de pythonw / bat / 2e fenêtre.

## Livré (code)

1. **Bouton** « Mains libres » (entre Parler et Masquer / Feedback), ON/OFF, `takefocus` + focus visible.
2. **Config** `mains_libres: bool` dans `presence.json`, défaut **False**.
3. **Host-agent** : JeV seulement si `mains_libres` True. WS `{"type":"options","mains_libres":…}` + champ sur invoke.
4. **Onboarding** étape 2/4 : Activer / Plus tard. Ne force pas ON.
5. **Libellé honnête** (retest Thomas) : ce n’est **pas** un micro ouvert. ON = `Mains libres : ON — encore Parler` + ligne *Pas un micro ouvert. Maintenez Parler ou {raccourci}*. VAD continu = hors scope.

## Première requête parfois perdue

**Pas de fix.** C10 : PTT avant `CANAL_PRET` ; l’Event ne file pas un pulse déjà relâché. Latch avant WS casserait `test_presence_premier_tour.py`. Warmup invoke : pas évident. Reste P1 dossier : le dire, répéter la phrase.

## Preuve tests (pytest, pas d’UI produit)

```
$ python -m py_compile native/presence/app.py native/presence/onboarding.py

$ python -m pytest -q dev/tests/test_presence_mains_libres.py \
    dev/tests/test_presence_onboarding.py dev/tests/test_c8_i18n.py \
    dev/tests/test_presence_premier_tour.py dev/tests/test_taquet_produit.py
52 passed, 2 skipped in 1.83s
```

Transport/JeV (conteneur) : 40 passed, 2 skipped (`options` WS + `jev_doit_ignorer`).

## Pour Thomas

- OFF = PTT comme avant.
- ON = encore Parler / Ctrl+Espace ; JeV filtre les apartés.
- Libellés honnêtes : au **prochain** lancement qu’il fera.
- Accueil : `--onboarding` quand il voudra.

NOTIFY=OG
ACTION: SendToAgent OG — lane PRESENCE-JEV-MAINS-LIBRES done
