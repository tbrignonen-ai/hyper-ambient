---
date: 2026-09-20
heure: ~19:20 Europe/Paris
type: out
lane: VAD-BANDE-VOIX
auteur: Cursor (Grok 4.6)
related: ["[[2026-09-20-BRIEF-CURSOR-VAD-BANDE-VOIX]]"]
---

# OUT — détection de voix par bande de fréquences

Périmètre respecté : `native/hostagent/windows_audio.py`, `dev/tests/test_vad_bande_voix.py` (créé), `dev/tests/test_ecoute_continue.py` (fixtures seulement). Presence non lancée. Aucune commande git. Fichiers interdits non touchés (`native/presence/app.py`, `src/*`, `dev/scripts/*`, `.env.local`).

## Diff résumé

`native/hostagent/windows_audio.py`
- `RATIO_BANDE_VOIX = 0.60`, bande 85–3400 Hz (`BANDE_VOIX_BAS_HZ` / `BANDE_VOIX_HAUT_HZ`).
- `_trame_voix` : `numpy.fft.rfft` sur la trame 20 ms ; rapport énergie_bande / énergie_totale. Évalué seulement si le RMS passe (`and` court-circuit).
- `_ingerer` : `au_dessus = rms >= seuil and _trame_voix(...)`.
- `_MIN_SEGMENT_MS = 700.0` (commentaire : Whisper hallucine sous ~1 s, mesure « Realise par Neo035 » sur 1,06–1,12 s).
- `_cloturer` : le silence qui clôt le tour ne compte pas dans le plancher (sinon 500 ms de voix + 700 ms de silence passaient).
- `PushToTalkCapture` inchangé.

`dev/tests/test_vad_bande_voix.py` (créé)
- Voise 150 Hz + harmoniques → parole ; bruit blanc / 50 Hz / 6000 Hz même RMS → pas parole ; silence → pas ; 500 ms voisé → jeté ; 1200 ms voisé + silence → un segment.

`dev/tests/test_ecoute_continue.py`
- `_parole` n'était pas du bruit blanc : un palier DC (0 Hz). Rejeté par le nouveau critère. Remplacé par une somme de sinusoïdes à 150 Hz + harmoniques, enveloppe variable. Aucun test désactivé.

## Bonus F0 (point 2) — non fait

Autocorrélation sur 320 échantillons : pas cher. Non implémenté : une fondamentale imposée entre 70 et 400 Hz rejetterait les trames non voisées (fricatives) et pourrait couper un tour réel. Le rapport spectral suffit déjà pour les quatre rejets demandés (blanc, 50 Hz, 6000 Hz, silence).

## Pytest (conteneur mother-core-dev, tel quel)

```
$ docker exec mother-core-dev sh -c "cd /workspace && python -m pytest -q dev/tests/test_vad_bande_voix.py dev/tests/test_ecoute_continue.py"
...............                                                          [100%]
15 passed in 0.27s
```

## Difficultés

- TDD : rouge d'abord 4 failed / 3 passed (blanc, 50 Hz, 6000 Hz, plancher 500 ms). Après le critère spectral, il restait le 500 ms : `_tour_ms` incluait les 700 ms de silence final, donc 1200 ≥ 700. Corrigé en mesurant `duree - silence_final`.
- Fixtures `_parole` en DC, pas en bruit blanc — même échec, même correctif voisé.
