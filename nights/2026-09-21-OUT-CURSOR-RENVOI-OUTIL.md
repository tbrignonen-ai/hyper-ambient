---
date: 2026-09-21
heure: ~04:05 Europe/Paris
type: out
lane: RENVOI-OUTIL
auteur: Cursor (Grok)
related:
  - "[[2026-09-21-BRIEF-CURSOR-RENVOI-OUTIL]]"
---

# OUT — renvoyer vers l'outil pour le détail

Périmètre demandé : `src/brain/`, `dev/scripts/serve_hostagent.py`,
`dev/tests/`. Pour que la voix dise la phrase et que le réglage existe
dans les menus : `src/i18n/__init__.py`, `native/presence/reglages_ui.py`,
`dev/scripts/parler_ecrit.py`. Aucune commande git.

## Ce qui a changé

Quand un mandat finit, elle dit le résumé, puis — seulement si c'est
une réduction d'un résultat plus riche — une phrase :

    Le détail est dans Codex si tu veux le lire.

Le nom est celui du mandat, pas celui du prompt. Une seule phrase,
ajoutée au résumé, sans offre commerciale. L'ancienne offre permanente
(« Tu veux le détail, ou que je te l'ouvre ? ») ne s'ajoute plus à
chaque arrivée ; elle reste le filet `sans_resume`.

`parler_ecrit` et le journal vocal passent par `phrase_arrivee`, plus
par le résumé seul : l'invitation est entendue et écrite.

Réglage `VOIX_RENVOI_OUTIL` (défaut activé). Case dans le bloc Voix
des menus. `0` / `off` / `false` / `non` : silence.

## Seuils

Deux, le premier est le plus honnête.

1. **`SEUIL_ECART_RENVOI = 400`** — surplus de `resultat_complet` sur
   `resume_voix`. C'est l'écart que le brief demandait. Un contrat JSON
   tenu (diff, analyse) le dépasse. Un décompte, même avec la liste des
   noms, reste dessous.
2. **`SEUIL_COMPLET_RICHE = 160`** — repli. Le pont Codex ne renvoie
   aujourd'hui que le texte parlable, donc `resume ~= complet` et
   l'écart est nul. On mesure alors la taille du complet, pas le nombre
   de mots prononcés. Un fait clos (« 16 », un décompte d'une phrase,
   ~70–80 caractères observés) tient dessous ; une explication du
   routeur (~200) passe dessus. 160 est à mi-chemin de la borne
   `resume_voix` (220).

Sans le second, la vérification live ne distinguait pas les deux
demandes : le pont aplatit tout en deux phrases parlables.

## TDD

Rouge d'abord (code intact) :

```
FFFF.FFFFF
9 failed, 1 passed in 0.86s
```

Le tour sans mandat passait déjà : il n'emprunte pas `phrase_arrivee`.
Les huit autres : invitation absente, case absente, clés i18n absentes.

Vert après :

```
............
12 passed in 1.11s
```

Riche → invitation. Court → pas d'invitation. Claude, pas Codex.
Réglage à `0` → silence. Tour « Bonjour » inchangé. Case activée par
défaut ; Enregistrer écrit `VOIX_RENVOI_OUTIL=0`.

Puis, rouge puis vert pour l'explication libre (~200 caractères,
resume = complet) : le repli à 160.

## Vérification demandée

```
docker exec mother-core-dev python dev/scripts/parler_ecrit.py \
  "Demande a Codex combien de fichiers Python contient le dossier src/brain."
```

```
conversation : /workspace/data/conversations/2026-09-21_04-01.md
→ Codex : Combien de fichiers Python (.py) contient le dossier src/brain ?
← Codex : Je demande à Codex. Je te préviens dès qu'il répond.
[deep 1947 ms] Je demande à Codex. Je te préviens dès qu'il répond.
← Codex : Codex a fini. Le dossier src/brain contient 16 fichiers Python, avec l’extension .py.
```

Pas de renvoi. Complet ~71 caractères.

```
docker exec mother-core-dev python dev/scripts/parler_ecrit.py \
  "Demande a Codex de m'expliquer comment fonctionne le routeur dans src/brain/router.py."
```

```
conversation : /workspace/data/conversations/2026-09-21_04-01.md
→ Codex : Explique-moi comment fonctionne le routeur dans src/brain/router.py.
← Codex : Je demande à Codex. Je te préviens dès qu'il répond.
[deep 1684 ms] Je demande à Codex. Je te préviens dès qu'il répond.
← Codex : Codex a fini. Le routeur classe d’abord chaque demande : les salutations ou ordres très simples vont vers le modèle local « réflexe », tandis que tout ce qui demande du raisonnement, des outils ou paraît ambigu part vers le modèle. Le détail est dans Codex si tu veux le lire.
```

Renvoi présent, nomme Codex.

## Pytest

Lane (conteneur) :

```
docker exec mother-core-dev python -m pytest \
  dev/tests/test_mandat.py \
  dev/tests/test_contrat_harnais.py \
  dev/tests/test_parler_ecrit.py \
  dev/tests/test_parite_anglaise.py \
  -q
```

```
86 passed, 2 xfailed in 1.50s
```

Suite complète (conteneur) :

```
docker exec mother-core-dev python -m pytest dev/tests -q \
  --ignore=dev/tests/test_health_sondes.py
```

```
4 failed, 1527 passed, 77 skipped, 2 xfailed, 41 warnings in 21.25s
```

Les quatre échecs sont les tests tkinter déjà connus (pas de `tkinter`
dans l'image). Pas de nouvel échec.

Six fichiers Tk (hôte) :

```
python -m pytest \
  dev/tests/test_presence_onboarding.py \
  dev/tests/test_presence_premier_tour.py \
  dev/tests/test_taquet_produit.py \
  dev/tests/test_taquet_wire2.py \
  dev/tests/test_reglages_ui.py \
  dev/tests/test_raccourcis_windows.py \
  -q -p no:cacheprovider
```

```
122 passed in 27.21s
```
