---
date: 2026-09-20
heure: ~23:00 Europe/Paris
type: out
lane: CHOIX-VOIX
auteur: Cursor (Grok)
related:
  - "[[2026-09-20-OUT-CURSOR-CHAMPS-EDITABLES]]"
  - "[[2026-09-20-OUT-CURSOR-MENUS-REGLAGES]]"
---

# OUT — Choix de voix dans Réglages

Périmètre : `native/presence/reglages_ui.py`, `src/i18n/__init__.py`,
`src/onboarding/sondes.py`, `dev/scripts/relance_hostagent.sh`,
`dev/tests/test_reglages_ui.py`, `dev/tests/test_onboarding_sondes.py`,
`dev/tests/test_taquet_wire2.py`. Aucun fichier interdit. Aucune
commande git. Aucune valeur de clé ici.

## Ce qui est livré

Un bloc **Voix** dans la catégorie **Sur votre machine**, entre
Modèle local et Clés et réglages. Marqueur local : la synthèse ne
quitte pas la machine.

Liste déroulante peuplée par `GET /v1/models` (`lister_voix_tts` dans
`src/onboarding/sondes.py`). Le menu n'est pas une liste figée dans
l'UI : il recopie `data[].voices`. Si le serveur est injoignable ou
rend une forme inconnue, repli John / Sofia / Aria / Jason / Leo, avec
la mention discrète « Liste de repli : le serveur vocal ne répond pas. »

La voix courante est lue dans `.env.local` (`MOUTH_VOICE_NAME`), sinon
dans `dev/scripts/carte_figee.env` (Sofia). Enregistrer écrit
`MOUTH_VOICE_NAME` dans `.env.local` via `poser_reglages`.

**Le changement n'est pas immédiat : il prend effet au prochain
redémarrage du moteur vocal** (`dev/scripts/relance_hostagent.sh`).
Vérifié : `serve_hostagent` construit `MagpieTTS(voice=…)` une fois au
chargement, et `charger_carte_figee` relit l'env au boot. Magpie
accepte une voix par requête, mais le host-agent ne la relit pas en
cours de route. `src/mouth/*` et `serve_hostagent.py` n'ont pas été
touchés.

## Bouton Écouter — non livré

Pas de bouton. Un bouton qui n'aurait pas joué l'audio était interdit.

Magpie écoute `127.0.0.1:8092` **dans** `mother-core-dev`.
`docker inspect` : le port 8092 n'est pas publié sur l'hôte (8000,
8001, 8090, 8091 seulement). Presence tourne sur Windows. Depuis
l'hôte, `http://127.0.0.1:8092/v1/models` n'est pas Magpie (réponse
404 d'un autre service). Jouer un extrait depuis la fenêtre Réglages
exigerait soit de publier Magpie, soit de modifier le host-agent
(interdit). La liste déroulante seule est livrée.

Depuis Presence Windows, le GET Magpie échoue donc aussi : le menu
affiche le repli et le dit. Dans le conteneur, le GET marche et le
menu suivra un modèle qui changerait ses voix.

## Plomberie — le chemin réel

Écrire `MOUTH_VOICE_NAME` dans `.env.local` ne suffisait pas :

1. `relance_hostagent.sh` exportait `MOUTH_VOICE_NAME` depuis la carte
   figée seulement (`lire_carte`).
2. `serve_hostagent.charger_env_local` ignore volontairement `MOUTH_*`.
3. `charger_carte_figee` **écrase** `MOUTH_VOICE_NAME` avec la carte,
   sauf si `MOUTH_VOICE_NAME_FORCE` est posé.

Chemin maintenant, sans toucher `serve_hostagent.py` :

1. Réglages → Enregistrer → `MOUTH_VOICE_NAME=Aria` dans `.env.local`.
2. `relance_hostagent.sh` lit `.env.local`. Si la clé est non vide et
   que `MOUTH_VOICE_NAME_FORCE` n'est pas déjà dans l'environnement,
   il fait `export MOUTH_VOICE_NAME_FORCE="$voix_locale"`.
3. Puis, comme avant : `MOUTH_VOICE_NAME="${MOUTH_VOICE_NAME_FORCE:-$(lire_carte …)}"`.
4. Au boot, `charger_carte_figee` voit `*_FORCE` et pose Aria.

Sans choix de voix, `.env.local` n'a pas la clé, FORCE n'est pas
exporté, la carte reste Sofia. Un opérateur qui pose déjà
`MOUTH_VOICE_NAME_FORCE` dans l'environnement gagne toujours.

## i18n

FR et EN dans `src/i18n/__init__.py`. Aucun texte en dur dans l'UI.
Espagnol hors périmètre. L'aide du bloc dit le redémarrage.

## Pytest

Référence demandée :

```
docker exec mother-core-dev python -m pytest dev/tests -q --ignore=dev/tests/test_health_sondes.py
```

Résultat :

```
4 failed, 1420 passed, 56 skipped, 2 xfailed
```

Référence : 1404 passed, 4 échecs pré-existants. Les 4 échecs sont
les mêmes (`tkinter` absent dans l'image : overlay / app / stdio
pythonw / palettes a11y). Aucun échec nouveau. Les tests Tk du menu
voix sont skippés dans le conteneur, comme les autres tests de
fenêtre Réglages.
