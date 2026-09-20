---
date: 2026-09-20
heure: ~18:50 Europe/Paris
type: out
lane: REVEIL-COURT
auteur: Cursor (Grok 4.6)
related: ["[[2026-09-20-BRIEF-CURSOR-REVEIL-COURT]]"]
---

# OUT — réveil court (« Oui ? ») en écoute continue

Périmètre respecté : `src/mouth/reveil.py` (nouveau), `src/mouth/secours.py`, `dev/scripts/serve_hostagent.py`, `dev/tests/test_reveil_court.py`. Presence non lancée. Aucune commande git. Fichiers interdits non touchés (`native/*`, `src/ears/*`, `src/i18n/__init__.py`, `.env.local`).

## Diff résumé

`src/mouth/reveil.py` (créé)
- Fonction pure `reveil_court_suffit(transcript, *, langue="fr")` : True si moins de 4 mots (hors ponctuation) **ou** s'il ne reste que le nom (hyper ambient / hyper ambiant / HA / MOTHER) et des mots vides (eh, dis, hey, bonjour, tu es là, …). Casse, accents, ponctuation ignorés.
- `PHRASES_REVEIL` fr/en/es, 3 formulations chacune, toutes < 30 caractères. `phrase_de_reveil` en tire une au hasard.

`src/mouth/secours.py`
- Défauts `reply=""`, `brain_injoignable=False`, `duree_audio_s=0.0` pour que `phrase_de_secours(transcript="", mains_libres=True)` reste None. Le silence muet en écoute continue n'est pas défait.

`dev/scripts/serve_hostagent.py`
- Après JeV (tour adressé), si `_mains_libres` et `reveil_court_suffit(transcript)` : log `JEV   : interpellation sans demande — reveil court`, prononce la phrase, termine le tour. **Pas d'appel BRAIN.**
- Appuyer-pour-parler inchangé : le bloc ne s'arme que si JeV tourne et que mains libres est vrai.

`dev/tests/test_reveil_court.py` (créé)
- Cas du brief (noms seuls, demande complète, chaîne vide, phrases courtes, non-régression secours) + pureté + câblage source.

## Pytest (conteneur mother-core-dev, tel quel)

```
$ docker exec mother-core-dev sh -c "cd /workspace && python -m pytest -q dev/tests/test_reveil_court.py dev/tests/test_secours.py"
.............................                                            [100%]
29 passed in 0.19s
```

## Difficultés

- TDD : 12 tests d'abord, rouge `ModuleNotFoundError: src.mouth.reveil` et `TypeError` sur `phrase_de_secours(transcript="", mains_libres=True)` (3 kwargs obligatoires). Vert 12/12 + 17 secours = 29.
- Heuristique en deux branches, pas un simple compteur : « eh hyper ambient tu es là » a plus de 4 mots mais aucune demande ; « hyper ambient, quelle heure est-il ? » a une demande. Les noms et « tu es là » se retirent par séquences de jetons, pas par tokens isolés (`il` / `tu` ne sont pas des mots vides).
- Les défauts de `phrase_de_secours` ne changent aucun appel existant ; ils rendent juste l'appel du brief valide.
