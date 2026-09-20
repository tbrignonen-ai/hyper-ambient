---
date: 2026-09-20
heure: ~21:40 Europe/Paris
type: out
lane: REGLAGES-V2
auteur: Cursor (Grok)
related: ["[[2026-09-20-OUT-CURSOR-MENUS-REGLAGES]]"]
---

# OUT — Réglages v2 : faux négatif des ponts, harnais sans clé API

Périmètre respecté : `src/onboarding/sondes.py`,
`native/presence/reglages_ui.py`, `dev/tests/test_onboarding_sondes.py`,
`dev/tests/test_reglages_ui.py`, libellés FR/EN dans
`src/i18n/__init__.py`. Aucun fichier interdit. Aucune commande git.
Aucun flux OAuth inventé. Aucune valeur de clé ici.

## Défaut 1 — le pont fonctionne, l'écran mentait

L'écran tourne sur l'hôte. `.env.local` garde
`host.docker.internal` parce que c'est l'adresse juste **pour
l'assistante dans le conteneur**. Depuis l'hôte cette adresse timeout ;
`127.0.0.1` répond (HTTP 401 sans jeton, donc joignable).

Quand la connexion échoue, `sonder_codex` / `sonder_claude` (et les
autres sondes HTTP) retentent **une fois** avec l'hôte alterné :
`host.docker.internal` ↔ `127.0.0.1`. Un 401 sur l'alterné n'est plus
« Codex ne répond pas » : c'est « refuse ce jeton », donc le pont est
là. L'URL stockée n'est pas réécrite.

## Défaut 2 — pas de clé API n'est pas une panne

`outil_cli_pret(nom)` avec `nom` valant `codex` ou `claude` : l'exécutable
est-il dans le PATH (`shutil.which`). Délai négligeable, aucune
exception ne sort, détail prononçable. La connexion d'abonnement n'est
**pas** vérifiée : lancer `claude` / `codex` pour tester l'OAuth
sortirait du client officiel. Le détail le dit.

L'écran :

1. Harnais Codex (CLI)
2. Harnais Claude Code (CLI)
3. Pont Codex
4. Pont Claude Code
5. Renfort distant — **optionnel**, après les harnais
6. Écoute JeV

Phrase du renfort : sans clé API, Claude Pro et ChatGPT Plus servent
déjà par les harnais ci-dessus.

## Pytest

Référence demandée :

```
docker exec mother-core-dev python -m pytest dev/tests -q --ignore=dev/tests/test_health_sondes.py
```

Résultat :

```
5 failed, 1398 passed, 35 skipped, 2 xfailed in 18.20s
```

Référence : 1389 passed, 5 failed. **Aucun échec nouveau.** Les cinq
échecs sont les pré-existants (`test_c11_identity`,
`test_presence_onboarding`, `test_presence_premier_tour`, deux de
`test_taquet_produit`). +9 tests (sondes, exécutés dans l'image).
+3 sauts Tk (l'image n'embarque pas `tkinter`).

Sur l'hôte Windows, `dev/tests/test_reglages_ui.py` :

```
17 passed, 1 skipped
```

## Fichiers

| Fichier | Rôle |
|---|---|
| `src/onboarding/sondes.py` | Hôte alterné + `outil_cli_pret` |
| `native/presence/reglages_ui.py` | Ordre des blocs, harnais CLI, Tout vérifier |
| `src/i18n/__init__.py` | Libellés FR/EN |
| `dev/tests/test_onboarding_sondes.py` | Contrat sondes |
| `dev/tests/test_reglages_ui.py` | Contrat écran |

Aucune valeur de clé dans ce rapport.
