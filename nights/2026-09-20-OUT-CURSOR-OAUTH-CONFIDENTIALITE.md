---
date: 2026-09-20
heure: ~21:40 Europe/Paris
type: out
lane: OAUTH-CONFIDENTIALITE
auteur: Cursor (Grok)
related:
  - "[[2026-09-20-OUT-CURSOR-REGLAGES-V2]]"
  - "[[2026-09-20-OUT-CURSOR-MENUS-REGLAGES]]"
---

# OUT — Réglages : marqueurs de confidentialité + détection des abonnements

Périmètre respecté : `native/presence/reglages_ui.py`,
`src/onboarding/sondes.py`, `src/i18n/__init__.py`,
`dev/tests/test_reglages_ui.py`, `dev/tests/test_onboarding_sondes.py`.
Aucun fichier interdit. Aucune commande git. Aucun flux OAuth inventé.
Aucun jeton lu, copié ou stocké. Aucune valeur de clé ici.

## Point 2 — ce qui reste, ce qui sort

Une phrase en haut de l'écran :

> Hyper Ambient ne collecte aucune donnée. Tout ce qui sort va vers les
> services que vous avez choisis.

Chaque bloc porte une pastille discrète et deux mots, pas un pavé :

| Bloc | Marqueur |
|---|---|
| Modèle local | reste sur votre machine |
| Harnais Codex / Claude Code | sort de votre machine |
| Ponts Codex / Claude Code | sort de votre machine |
| Renfort distant | sort de votre machine |
| Écoute JeV | sort de votre machine |
| Recherche web | sort de votre machine |
| Clés et réglages | reste sur votre machine |

Les trois blocs ajoutés (modèle local, recherche, clés) sont
informatifs : pas de champ, pas de bouton Vérifier. Les pastilles vert /
rouge des sondes restent celles de la vérification, ailleurs.

## Point 1 — Détecter mes abonnements

Un bouton unique, juste au-dessus des deux harnais. Un clic appelle
`outil_cli_pret` pour `codex` puis `claude`, hors fil Tk, et rend
l'état dans chaque harnais.

Ce qu'on sait dire de façon fiable et rapide :

- **absent** — l'exécutable n'est pas dans le PATH. Commande PowerShell
  d'installation puis de connexion.
- **installé** — le programme est là. On **n'affirme pas** qu'il est
  connecté.

Ce qu'on ne distingue pas : connecté / pas connecté. Lire un fichier
d'OAuth serait contraire aux conditions. Lancer `claude` ou `codex` assez
longtemps pour en être sûr dépasse un clic de réglages, et un chemin
de credentials deviné dirait « pas connecté » à un fondateur qui l'est.
Le libellé le dit : *la connexion de l'abonnement n'a pas été
vérifiée*, plus la commande officielle à taper.

| État | PowerShell |
|---|---|
| Codex absent | `npm install -g @openai/codex; codex login` |
| Codex installé | `codex login` |
| Claude absent | `npm install -g @anthropic-ai/claude-code; claude` |
| Claude installé | `claude` |

## Libellés

Chaque clé nouvelle existe en français et en anglais dans
`src/i18n/__init__.py`. L'espagnol reste hors périmètre.

## Pytest

Référence demandée :

```
docker exec mother-core-dev python -m pytest dev/tests -q --ignore=dev/tests/test_health_sondes.py
```

Résultat :

```
5 failed, 1402 passed, 36 skipped, 2 xfailed in 17.90s
```

Référence : 1398 passed, 5 failed. **Aucun échec nouveau.** Les cinq
échecs sont les pré-existants (`test_c11_identity`,
`test_presence_onboarding`, `test_presence_premier_tour`, deux de
`test_taquet_produit`). +4 tests exécutés dans l'image. +1 saut Tk
(l'image n'embarque pas `tkinter` ; le nouveau test fenêtré du bouton
s'ajoute aux sauts déjà là).

Sur l'hôte Windows, `dev/tests/test_reglages_ui.py` et
`dev/tests/test_onboarding_sondes.py` plus la parité FR/EN :

```
62 passed, 2 skipped, 2 xfailed
```

## Fichiers

| Fichier | Rôle |
|---|---|
| `native/presence/reglages_ui.py` | Marqueurs, blocs info, bouton unique |
| `src/onboarding/sondes.py` | Commandes PowerShell, `detecter_abonnements` |
| `src/i18n/__init__.py` | Libellés FR/EN |
| `dev/tests/test_reglages_ui.py` | Contrat écran |
| `dev/tests/test_onboarding_sondes.py` | Contrat sondes |

Aucune valeur de clé dans ce rapport.
