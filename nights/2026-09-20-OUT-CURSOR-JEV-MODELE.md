---
date: 2026-09-20
heure: ~22:10 Europe/Paris
type: out
lane: JEV-MODELE
auteur: Cursor (Grok)
related:
  - "[[2026-09-20-OUT-CURSOR-REGLAGES-V3]]"
  - "[[2026-09-20-OUT-CALIBRAGE-JEV]]"
---

# OUT — Nom du modèle JeV configurable

Périmètre respecté : `src/ears/jev_reflexe.py`, `src/onboarding/sondes.py`,
`native/presence/reglages_ui.py`, `src/i18n/__init__.py`, tests dans
`dev/tests/`. Aucun fichier interdit. Aucune commande git. Aucune
valeur de clé ici.

Le défaut ne change pas : sans `TYPESAFE_MODEL`, le client envoie
`jev-latest`. Quelqu'un qui ne touche à rien ne voit aucune différence.

## 1. Lecture à l'appel, pas à l'import

`JEV_MODEL` reste la constante `"jev-latest"`. Une fonction
`modele_jev()` lit `TYPESAFE_MODEL` à chaque appel. Vide ou blanc :
repli sur `jev-latest`. `JevReflexe.evaluate` passe par cette
fonction, donc un changement d'environnement après construction du
client est pris en compte sans redémarrage du process Python.

## 2. Écran Réglages

Le bloc JeV (TypeSafe AI) a maintenant deux champs, dans le même
ordre que le bloc Modèle distant (nom d'abord, clé ensuite) :

1. **Nom du modèle (TYPESAFE_MODEL)** — exemple `jev-latest`
2. **Clé JeV**

Aucun texte en dur : FR et EN dans `src/i18n/__init__.py`. L'espagnol
reste hors périmètre.

## 3. Sonde

`sonder_jev(cle, client=None, modele=None)` : le troisième paramètre
est optionnel, en fin de signature. Les appelants existants ne
cassent pas. Vide → `modele_jev()`. `sonder_tout` lui passe
`TYPESAFE_MODEL` s'il est dans les réglages. Le bouton Vérifier du
bloc JeV fait de même.

## 4. `poser_reglages` écrit bien `TYPESAFE_MODEL`

`poser_reglages` n'a pas de liste blanche : il écrit toute clé au
nom valide. L'écran passe `TYPESAFE_MODEL` via `enregistrer_saisie`.
Preuve : `test_poser_reglages_ecrit_typesafe_model`.

`CLES_ONBOARDING` dans `src/onboarding/reglages.py` ne liste pas
encore `TYPESAFE_MODEL`. Ce n'est pas un filtre d'écriture. Hors
périmètre, non touché.

## 5. Host-agent — à faire ailleurs

`dev/scripts/relance_hostagent.sh` lit `.env.local` et exporte
`TYPESAFE_API_KEY`. **Il n'exporte pas `TYPESAFE_MODEL`.** Tant que
ce nom n'y est pas ajouté, un réglage posé dans l'écran n'arrivera
pas dans l'environnement du host-agent après relance : les mains
libres resteront sur `jev-latest`.

À ajouter, sans toucher au reste du script :

```
TYPESAFE_MODEL="$(lire_env_local TYPESAFE_MODEL)"
export TYPESAFE_MODEL
```

à côté de `TYPESAFE_API_KEY` (lignes 35 et 42).

Note hors script, même cause : `charger_env_local` dans
`dev/scripts/serve_hostagent.py` n'injecte que `_CLES_OUTILS`, où
`TYPESAFE_MODEL` n'est pas. Un `docker start` sans relance ne
propagerait pas non plus le nom. Hors périmètre, non touché.

## Pytest

Référence demandée :

```
docker exec mother-core-dev python -m pytest dev/tests -q --ignore=dev/tests/test_health_sondes.py
```

Résultat :

```
5 failed, 1411 passed, 36 skipped, 2 xfailed in 19.28s
```

Référence : 1405 passed, 5 failed. **Aucun échec nouveau.** Les cinq
échecs sont les pré-existants (`test_c11_identity`,
`test_presence_onboarding`, `test_presence_premier_tour`, deux de
`test_taquet_produit`). +6 tests (lecture env à l'appel, paramètre
sonde, env sonde, `sonder_tout`, libellés FR, écriture
`TYPESAFE_MODEL`).

Sur l'hôte Windows, `dev/tests/test_reglages_ui.py` :

```
23 passed, 2 skipped
```

Les tests fenêtrés voient le champ, l'exemple `jev-latest`, et
l'ordre nom puis clé. L'image Docker n'a pas Tk : ces tests-là
sautent dans le conteneur, comme avant.

## Fichiers

| Fichier | Rôle |
|---|---|
| `src/ears/jev_reflexe.py` | `modele_jev()`, lecture `TYPESAFE_MODEL` à l'appel |
| `src/onboarding/sondes.py` | Paramètre optionnel `modele`, `sonder_tout` |
| `native/presence/reglages_ui.py` | Champ JeV, exemple, sonde |
| `src/i18n/__init__.py` | Libellés FR/EN |
| `dev/tests/test_jev_reflexe.py` | Env lu après construction |
| `dev/tests/test_onboarding_sondes.py` | Signature, paramètre, `sonder_tout` |
| `dev/tests/test_reglages_ui.py` | Bloc, libellés, écriture |

Aucune valeur de clé dans ce rapport.
