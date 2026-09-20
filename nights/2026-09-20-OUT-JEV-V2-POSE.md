---
date: 2026-09-20
heure: ~20:00 Europe/Paris
type: out
lane: JEV-V2
auteur: Cursor (Grok 4.6)
related: ["[[2026-09-20-BRIEF-CURSOR-JEV-V2]]", "[[2026-09-20-OUT-JEV-QUESTIONS-V2]]"]
---

# OUT — poser JeV V2 (questions d'adresse + regle de combinaison)

Source appliquee telle quelle : `nights/2026-09-20-OUT-JEV-QUESTIONS-V2.md`.
Pas de commit. Fichiers interdits non touches (`native/*`, `src/mouth/*`,
`src/brain/*`, `.env.local`). `nom_du_produit_prononce` et `FenetreConversation`
intacts. `jev_ignore_tour` / `jev_doit_ignorer` continuent de lire
`signals.addressed_to_mother`.

La source porte **sept** identifiants d'adresse (pas six) : le brief comptait
les questions positives + vetos sans le monologue ; la mesure et la regle
utilisent les sept. Espagnol reporte.

## Diff resume

`src/ears/jev_reflexe.py`
- `addressed_to_mother` remplace par les 7 noul V2. Les 12 autres questions
  (`real_interruption`, `phrase_finished`, …) restent. Contrat : 19 jugements
  dans le meme POST. `_validated_answers` exige `set(raw_answers) == set(QUESTIONS)`.
- `addressed_v2` : fonction pure. Seuils nommes, commentes, copies de la source :
  nom >= 0.50 ; interpellation >= 0.55 ou demande >= 0.50 ; veto tiers >= 0.55,
  lu/diffuse >= 0.65, rapporte >= 0.50, monologue >= 0.70.
- `JevSignals.addressed_to_mother` calcule par `addressed_v2`, plus par
  `noul_true`.

`src/i18n/__init__.py`
- `QUESTIONS_EN` : memes identifiants, consignes traduites. Pas de table ES.

`dev/scripts/serve_hostagent.py`
- Point de decision inchange : `not signals.addressed_to_mother`.

`dev/tests/test_jev_v2.py` (cree)
- Cas du brief + chaque seuil juste dessous / juste dessus.
- Corpus mesure : 24 adressees, 22 non adressees.
- Branchement : `evaluate` (transport fake) suit la regle.

`dev/tests/test_jev_reflexe.py`
- Doubles d'answers alignes sur les 19 identifiants (sinon validation → None).

## Pytest (conteneur mother-core-dev, tel quel)

```
$ docker exec mother-core-dev sh -c "cd /workspace && python -m pytest -q dev/tests/test_jev_v2.py dev/tests/test_jev_reflexe.py dev/tests/test_jev_seuil_et_nom.py dev/tests/test_fenetre_conversation.py dev/tests/test_jev_branchement.py"
....................................                                     [100%]
36 passed in 1.14s
```

Mesure reproduite : 0 faux negatif / 24 adressees, 0 faux positif / 22 non adressees.
