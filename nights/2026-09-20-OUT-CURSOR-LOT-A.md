---
date: 2026-09-20
heure: ~21:00 Europe/Paris
type: out
lane: ONBOARDING-V2 LOT A
auteur: Cursor (Opus)
related: ["[[2026-09-20-SPEC-ONBOARDING-V2]]"]
---

# OUT — Lot A, les sondes

Perimetre respecte : `src/onboarding/__init__.py`, `src/onboarding/sondes.py`,
`dev/tests/test_onboarding_sondes.py`. Aucun autre fichier. Aucune commande git.

## API

`Sonde(service, ok, detail, latence_ms)` et les cinq fonctions imposees, au
caractere pres. `detail` distingue les trois causes dicibles (jeton absent,
injoignable, jeton refuse) sans URL, sans code HTTP, sans trace. Delai borne a
5 s. Aucune exception ne sort. `sonder_tout` lance les quatre sondes en
parallele. Client HTTP injectable ; les tests ne touchent pas le reseau.

Formes d'appel : celles des ponts deja la (`POST` + Bearer). Codex et Claude
envoient une question vide : le pont authentifie sans lancer le CLI (un PONG
reel depasse 5 s). JeV vise `JEV_ENDPOINT` / `JEV_MODEL`.

## Pytest

```
$ docker exec mother-core-dev python -m pytest dev/tests/test_onboarding_sondes.py -q
...................                                                      [100%]
19 passed in 5.76s
```

Hote Windows, meme fichier : `19 passed in 5.28s`. La duree vient du test qui
prouve le plafond de cinq secondes.

Aucune valeur de cle dans ce rapport.
