---
date: 2026-09-20
heure: ~21:30 Europe/Paris
type: out
lane: MENUS-REGLAGES
auteur: Cursor (Grok)
related: ["[[2026-09-20-SPEC-ONBOARDING-V2]]"]
---

# OUT — Écran Réglages dans Presence

Périmètre respecté : `native/presence/reglages_ui.py`,
`dev/tests/test_reglages_ui.py`, le bouton d'ouverture dans
`native/presence/app.py`, libellés FR/EN dans `src/i18n/__init__.py`.
Aucun fichier interdit. Aucune commande git. Aucune valeur de clé ici.

L'onboarding conversationnel n'est pas touché. Les modules
`src.onboarding.sondes` et `src.onboarding.reglages` sont utilisés tels
quels, sans réécriture.

## Ce qui est livré

Une fenêtre **Réglages**, ouverte à tout moment depuis un bouton de la
fenêtre principale. Quatre blocs :

1. Renfort distant — adresse, modèle, clé
2. Codex — adresse, jeton
3. Claude Code — adresse, jeton
4. JeV — clé

Chaque bloc a sa phrase d'usage, un bouton **Vérifier** (sonde du
service, pastille verte ou rouge + `detail`), et les champs masqués
pour les clés. **Enregistrer** écrit par `poser_reglages`. **Tout
vérifier** appelle `sonder_tout`.

## Contrats tenus

- Aucune sonde sur le fil Tk. Les valeurs sont lues sur le fil de
  l'interface, le travail part dans un fil `reglages-sonde`, le rendu
  revient par une file pompée avec `after()` — le même schéma que
  `SessionVocale`.
- Pendant une vérification le bouton se désactive et affiche
  « Je vérifie… ».
- Une clé déjà posée n'apparaît que par ses quatre derniers
  caractères. Le champ masqué reste vide. Si l'utilisateur ne le
  retouche pas, la clé n'est pas réécrite.
- Les valeurs publiques de `.env.local` sont préchargées. Le
  `.env.local` du dépôt n'est jamais ouvert par les tests.
- Toplevel sans `grab` : la fenêtre principale reste utilisable.
  Tab / Entrée / Échap. Échap ferme les réglages, pas l'application.

## Pytest

Référence demandée :

```
docker exec mother-core-dev python -m pytest dev/tests -q --ignore=dev/tests/test_health_sondes.py
```

Résultat :

```
5 failed, 1389 passed, 32 skipped, 2 xfailed in 16.82s
```

Les cinq échecs sont les pré-existants : `test_c11_identity`,
`test_presence_onboarding` (`test_orbe_repos_reste_lisible`),
`test_presence_premier_tour`, et deux de `test_taquet_produit`. Aucun
échec nouveau.

`dev/tests/test_reglages_ui.py` dans le même conteneur (sans Tk) :

```
8 passed, 7 skipped
```

Les sept sauts sont les tests fenêtrés : l'image `mother-core-dev`
n'embarque pas `tkinter`. La logique (masquage, non-réécriture,
fil séparé, `poser_reglages`) passe sans interface. Sur l'hôte
Windows, les tests Tk du même fichier passent quand Tcl est
disponible.

Parité FR/EN (`test_parite_anglaise`, `test_c8_i18n`) : inchangée,
29 passed, 2 xfailed (table ES hors périmètre).

## Fichiers

| Fichier | Rôle |
|---|---|
| `native/presence/reglages_ui.py` | Fenêtre + logique testable |
| `native/presence/app.py` | Bouton Réglages, `ouvrir_reglages` |
| `src/i18n/__init__.py` | Libellés `ui.settings` et `reglages.*` FR/EN |
| `dev/tests/test_reglages_ui.py` | Contrat |

Aucune valeur de clé dans ce rapport.
