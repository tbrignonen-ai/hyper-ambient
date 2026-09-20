---
date: 2026-09-20
heure: ~22:00 Europe/Paris
type: out
lane: REGLAGES-V3
auteur: Cursor (Grok)
related:
  - "[[2026-09-20-OUT-CURSOR-REGLAGES-V2]]"
  - "[[2026-09-20-OUT-CURSOR-MENUS-REGLAGES]]"
  - "[[2026-09-20-OUT-CURSOR-OAUTH-CONFIDENTIALITE]]"
---

# OUT — Réglages v3 : libellés, catégories, modèle distant

Périmètre respecté : `native/presence/reglages_ui.py`,
`src/i18n/__init__.py`, `dev/tests/test_reglages_ui.py`.
Aucun fichier interdit. Aucune commande git. Aucune logique de sonde,
d'écriture ou de masquage changée. Aucune valeur de clé ici.

L'écran rassurait mal : « sort de votre machine » à côté des ponts
Codex et Claude. Ces ponts sont locaux. Le texte le dit maintenant.

## Problème 1 — le mot qui inquiétait

Le marqueur binaire (« reste ici » / « sort de votre machine ») est
remplacé par un libellé par bloc, qui commence par **Données**
(anglais : **Data**). Une pastille de couleur reste : verte si rien
ne quitte la machine, ambre si des données partent vers un service
choisi.

| Bloc | Libellé |
|---|---|
| Modèle local | Données locales. Rien ne quitte cette machine. |
| Clés et réglages | Données locales. Fichier sur cette machine. |
| Harnais / Pont Codex | Données locales. Communique avec le pont local Codex, qui utilise votre propre abonnement. |
| Harnais / Pont Claude Code | Données locales. Communique avec le pont local Claude Code, qui utilise votre propre abonnement. |
| Modèle distant | Données envoyées au modèle distant que vous avez choisi. |
| JeV (TypeSafe AI) | Données envoyées à TypeSafe AI. Optionnel. |
| Recherche web | Données envoyées au moteur dont vous avez posé la clé. |

Les ponts et harnais ne sont plus marqués comme une sortie. Hyper
Ambient ne les exfiltre pas : le pont tourne ici, l'outil officiel
parle ensuite à l'abonnement déjà installé.

## Problème 2 — trois catégories

Ordre à l'écran :

1. **Sur votre machine** — Modèle local, Clés et réglages
2. **Vos outils, vos abonnements** — Harnais Codex, Harnais Claude Code, Pont Codex, Pont Claude Code (bouton « Détecter mes abonnements » en tête de cette catégorie)
3. **Services distants** — Modèle distant, JeV (TypeSafe AI), Recherche web

Les harnais restent dans la catégorie 2 : ce sont les outils et
abonnements de l'utilisateur, pas un service distant. Aucun bloc
supprimé, aucun champ retiré.

## Problème 3 — Modèle distant

« Renfort distant » s'appelle **Modèle distant**. Trois phrases
courtes : fortement recommandé pour les demandes difficiles ;
préférer un modèle dont on peut désactiver le raisonnement (l'attente
silencieuse à l'oral) ; on peut aussi passer par Codex ou Claude Code
déjà connectés, sans clé API.

Le champ **Nom du modèle (BRAIN_MODEL)** est le premier du bloc,
distinct de l'adresse et de la clé, avec un exemple
(`gpt-4.1`, `claude-sonnet-4`).

## Problème 4 — ce que fait Vérifier

Près des boutons, toujours visible :

> Vérifier appelle réellement le service, avec un délai de cinq
> secondes. Si un test échoue, les réglages restent modifiables à
> la main dans le fichier `.env.local`.

Le délai de cinq secondes est celui déjà posé (`DELAI_S = 5.0`).
Si une sonde échoue, la même phrase `.env.local` apparaît aussi
sur la ligne de statut.

## Libellés

Chaque clé nouvelle ou changée existe en français et en anglais
dans `src/i18n/__init__.py`. Aucun texte en dur dans l'interface.
L'espagnol reste hors périmètre. La parité des clés FR/EN est
tenue (plus de « reste ici » / « sort de votre machine »).

## Pytest

Référence demandée :

```
docker exec mother-core-dev python -m pytest dev/tests -q --ignore=dev/tests/test_health_sondes.py
```

Résultat :

```
5 failed, 1405 passed, 36 skipped, 2 xfailed in 20.49s
```

Référence : 1402 passed, 5 failed. **Aucun échec nouveau.** Les cinq
échecs sont les pré-existants (`test_c11_identity`,
`test_presence_onboarding`, `test_presence_premier_tour`, deux de
`test_taquet_produit`). +3 tests (catégories, libellés Données FR,
libellés Data EN).

Sur l'hôte Windows, `dev/tests/test_reglages_ui.py` :

```
23 passed
```

## Fichiers

| Fichier | Rôle |
|---|---|
| `native/presence/reglages_ui.py` | Catégories, libellé Données, ordre BRAIN_MODEL, phrase Vérifier |
| `src/i18n/__init__.py` | Libellés FR/EN |
| `dev/tests/test_reglages_ui.py` | Contrat écran |

Aucune valeur de clé dans ce rapport.
