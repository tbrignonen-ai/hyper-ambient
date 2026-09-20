# BRIEF Cursor — parite anglaise du produit
Lead : Claude (Opus). 2026-09-20 ~19h40.

Le produit annonce trois langues (fr / en / es). Le francais est teste et valide ;
l'anglais ne l'est pas. Objectif : prouver la parite, ou lister precisement ce qui
manque.

## Perimetre STRICT
- `dev/tests/test_parite_anglaise.py` (a creer)
- Corrections MINIMES dans `src/i18n/__init__.py` UNIQUEMENT si un libelle manque
  en anglais. Toute autre correction : tu la SIGNALES dans l'OUT, tu ne la fais pas.

INTERDIT : `native/*`, `dev/scripts/*`, `src/ears/*`, `src/mouth/*`, `.env.local`.
N'EXECUTE AUCUNE COMMANDE GIT.

## Travail
1. Inventorie toutes les cles de `ui_presence()` et de `questions_jev()`. Verifie
   que CHAQUE cle existe en `fr`, `en` et `es`, sans valeur vide ni reliquat francais.
2. Ecris des tests qui echouent si une langue perd une cle a l'avenir (compare les
   jeux de cles entre les trois tables, ne les liste pas a la main).
3. Verifie que `HA_LANG=en` bascule reellement : `ui_presence()`, `questions_jev()`,
   et les phrases de `src/mouth/secours.py` et `src/mouth/reveil.py`.
4. Verifie qu'aucune chaine visible par l'utilisateur n'est codee en dur en francais
   dans `native/presence/app.py` (lecture seule : tu SIGNALES, tu ne corriges pas).

## Preuve
    docker exec mother-core-dev sh -c "cd /workspace && python -m pytest -q dev/tests/test_parite_anglaise.py dev/tests/test_c8_i18n.py"
OUT dans `nights/2026-09-20-OUT-TESTS-ANGLAIS.md`. Ne reponds que OK.
