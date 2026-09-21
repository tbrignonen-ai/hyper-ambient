---
date: 2026-09-20
heure: ~23:15 Europe/Paris
type: out
lane: ACCENT
auteur: Cursor (Grok)
related:
  - "[[2026-09-20-OUT-CURSOR-CHOIX-VOIX]]"
---

# OUT — Accent de la voix dans Réglages

Périmètre : `native/presence/reglages_ui.py`, `src/i18n/__init__.py`,
`src/onboarding/sondes.py`, `dev/scripts/relance_hostagent.sh`,
`dev/tests/test_reglages_ui.py`, `dev/tests/test_onboarding_sondes.py`,
`dev/tests/test_taquet_wire2.py`. Aucun fichier interdit. Aucune
commande git. Aucune valeur de clé ici.

## Ce qui est livré

Un second menu **Accent**, à côté de celui des voix, dans le même bloc
Voix. Il pilote `MOUTH_LANGUAGE` indépendamment de la langue de
l'interface.

Le menu n'est pas une liste figée : il recopie `data[].languages` du
même `GET /v1/models` que les voix (`lister_voix_tts`). Aujourd'hui
Magpie rend en-US, es-ES, de-DE, fr-FR, it-IT, vi-VN, hi-IN. Un code
inconnu s'affiche quand même, en libellé humain de repli.

Libellés pour un humain, jamais un code d'ingénieur :

- défaut : **Aucun accent** (EN : No accent)
- les autres : Accent anglais, Accent espagnol, Accent allemand,
  Accent français, Accent italien, Accent vietnamien, Accent hindi

Sous le menu, la phrase du fondateur : un accent rend la voix plus
charmante, un peu moins facile à comprendre.

## Défaut inchangé

Sans choix explicite, le comportement actuel est conservé. La carte
figée reste `MOUTH_LANGUAGE=fr`. « Aucun accent » écrit `fr`, pas
`fr-FR`. Magpie peut lister `fr-FR` à part, comme Accent français ;
ce n'est pas le défaut.

Sans `MOUTH_LANGUAGE` dans `.env.local`, `MOUTH_LANGUAGE_FORCE` n'est
pas exporté, la carte reste `fr`. Un opérateur qui pose déjà
`MOUTH_LANGUAGE_FORCE` dans l'environnement gagne toujours.

## Bloc discret

Le bloc Voix est en bas de **Sur votre machine** (après Clés et
réglages), replié par défaut. Titre et marqueur local restent visibles ;
les menus s'ouvrent d'un clic sur le titre. On change de voix une fois.

## Bouton Écouter

Le bouton n'existait pas (livraison voix : Magpie n'est pas publié sur
l'hôte, un bouton muet était interdit). Il est là maintenant. Il envoie
**les deux** réglages, voix et accent, dans un `POST /v1/audio/speech`
(`synthetiser_extrait_tts` dans `src/onboarding/sondes.py`), puis joue
le WAV. L'extrait est une phrase courte dans la langue de l'interface,
pour entendre le français avec un accent anglais si on l'a choisi.

Si Magpie ne répond pas, le statut dit que l'extrait n'a pas pu être
joué. Même limite qu'hier : depuis Presence Windows, `:8092` n'est pas
Magpie (port non publié). Dans le conteneur, le POST suit le modèle.

## Plomberie — le même chemin que la voix

1. Réglages → Enregistrer → `MOUTH_LANGUAGE=en-US` dans `.env.local`.
2. `relance_hostagent.sh` lit `.env.local`. Si la clé est non vide et
   que `MOUTH_LANGUAGE_FORCE` n'est pas déjà dans l'environnement,
   il fait `export MOUTH_LANGUAGE_FORCE="$langue_locale"`.
3. Puis, comme avant : `MOUTH_LANGUAGE="${MOUTH_LANGUAGE_FORCE:-$(lire_carte …)}"`.
4. Au boot, `charger_carte_figee` voit `*_FORCE` et pose la phonétique.

`serve_hostagent.py` n'a pas été touché.

## i18n

FR et EN dans `src/i18n/__init__.py`. Aucun texte en dur dans l'UI.
Espagnol hors périmètre.

## Pytest

Référence demandée :

```
docker exec mother-core-dev python -m pytest dev/tests -q --ignore=dev/tests/test_health_sondes.py
```

Résultat :

```
4 failed, 1431 passed, 58 skipped, 2 xfailed
```

Référence d'entrée : 1423 passed, 4 échecs pré-existants. Les 4 échecs
sont les mêmes (`tkinter` absent dans l'image : overlay / app / stdio
pythonw / palettes a11y). Aucun échec nouveau. Huit tests ajoutés
(langues Magpie, relance FORCE, libellés, enregistrement, Écouter).
Les tests Tk du menu sont skippés dans le conteneur, comme les autres
tests de fenêtre Réglages.
