---
date: 2026-09-21
heure: ~01:50 Europe/Paris
type: out
lane: NUIT-A
auteur: Cursor (Grok)
related:
  - "[[2026-09-21-BRIEF-CURSOR-NUIT-A]]"
---

# OUT — Nuit A : chemin écrit, transcriptions, hallucinations EARS

Périmètre : `dev/scripts/serve_hostagent.py`, `dev/scripts/parler_ecrit.py`,
`src/ears/silence.py`, `src/ears/faster_whisper_asr.py`, tests associés.
`src/brain/tool_loop.py` intact (paramètre `tool_choice` conservé).
`src/brain/router.py` intact (`nomme_un_harnais` conservé).
`carte_figee.env`, `.env.local`, `DONNEES*.md`, `README.md` intacts.
Aucune commande git.

## Tâche 1 — forçage `tool_choice` retiré

`tool_choice_si_harnais` et son câblage dans `_flux_brain` sont partis.
`run_tool_loop(..., tool_choice=)` reste : API d'échappatoire, plus appelée
par défaut. Un prompt « qu'est-ce que Codex ? » ne force plus d'outil.

Les trois tests qui couvraient le forçage côté serveur sont remplacés par
`test_serve_hostagent_n_a_plus_de_forcage_tool_choice`. Les tests
`test_tool_choice_*` de `tool_loop.py` restent verts.

## Tâche 2 — chemin écrit

`monter_cerveau()` et `flux_cerveau()` extraits de `HostPipeline` :
cerveau, registre, porte, mandats, veille. `load()` et
`dev/scripts/parler_ecrit.py` appellent les mêmes fonctions.

`parler_ecrit.py` : stdin/stdout, pas d'EARS, pas de MOUTH, pas de
websocket. Affiche `[canal N ms]`, les appels d'outil, les mandats à
l'arrivée. Mode non interactif : une question en argument.

    python3 dev/scripts/parler_ecrit.py
    python3 dev/scripts/parler_ecrit.py "Bonjour, comment vas-tu ?"

## Tâche 3 — transcriptions relisibles

Un fichier Markdown par conversation, écrit à chaque tour (flush + fsync).

En conteneur : `/workspace/data/conversations/YYYY-MM-DD_HH-MM.md`
(volume `./data` du compose — même mécanisme que les autres écritures
du host-agent). Hors conteneur : `%LOCALAPPDATA%\hyper-ambient\conversations`.

Contenu : heure, locuteur, texte. Outils / mandats en une ligne
(`→ Codex : …` / `← Codex : …`). Aucun secret.

**À signaler pour `DONNEES.md` / `DONNEES.en.md`** (non édités ici,
un autre agent les tient) : ces fichiers de conversation sont locaux,
ne quittent pas la machine, vivent sous le volume `data/conversations`
(hôte) ou `%LOCALAPPDATA%\hyper-ambient\conversations`.

### Preuve de lecture depuis l'hôte

Écriture dans le conteneur via `nouveau_fichier_conversation` +
`ecrire_ligne_conversation` :

    dossier_conversations= /workspace/data/conversations
    fichier_conteneur= /workspace/data/conversations/2026-09-21_01-45.md

Lecture réelle depuis l'hôte,
`D:\BGB Training\MOTHER-dev\data\conversations\2026-09-21_01-45.md` :

```
# Conversation 2026-09-21 01:45

01:45:00  Toi  preuve lecture hote
```

Le fichier arrive bien au volume monté. Ce n'est pas
`%LOCALAPPDATA%\hyper-ambient\conversations` : le compose n'expose
que `./data` et `./logs`. Pas de volume ajouté (hors périmètre).

## Tâche 4 — EARS, bruit, mains libres

`faster_whisper_asr._decode` remonte `no_speech_prob` et `avg_logprob`.
Défense principale : seuil 0.6 / −1.0 (ceux de faster-whisper).
Filet textuel ensuite (casse / accents) : « sous-titrage »,
« sous-titres réalisés par », « amara.org », « merci d'avoir regardé »,
« abonnez-vous », « subtitles by », « thanks for watching ».

`jeter_tour_bruit(..., mains_libres=)` : hors mains libres, on ne jette
rien (appui Parler = l'utilisateur a décidé de parler). En mains libres,
journal `EARS  : segment rejeté (bruit) "…"` puis return : pas de
fenêtre, pas de réveil, pas de parole.

## Pytest

TDD : rouge d'abord (ImportError / AttributeError / AssertionError sur
les symboles absents), puis vert.

Commande demandée, telle quelle, **sur l'hôte Windows** :

```
python -m pytest dev/tests -q
```

```
ERROR test_debit.py / test_piper_taux.py / test_pocket_transposition.py
ERROR test_qwen3_asr.py / test_supertonic_tts.py / test_transposition.py
Interrupted: 6 errors during collection
```

scipy / torch absents de l'interpréteur hôte. Suite réelle dans le
conteneur, comme les OUT des 19–20 sept
(`--ignore=dev/tests/test_health_sondes.py` : `handlers` du worker
santé, hors périmètre).

```
docker exec mother-core-dev python -m pytest dev/tests -q --ignore=dev/tests/test_health_sondes.py
```

```
8 failed, 1458 passed, 61 skipped, 2 xfailed, 41 warnings in 18.13s
```

Les 8 échecs sont antérieurs et hors de cette lane :

- `test_carte_figee` / `test_taquet_*` : attendent `llamacpp`, la carte
  figée est maintenant `router` (état acquis du brief — fichier non touché).
- `test_presence_*` / `test_assurer_stdio_*` / palettes : `tkinter`
  absent du conteneur.

Tests de cette nuit, isolés dans le conteneur :

```
docker exec mother-core-dev python -m pytest \
  dev/tests/test_ears_silence.py \
  dev/tests/test_conversations.py \
  dev/tests/test_parler_ecrit.py \
  dev/tests/test_ears_hotwords.py \
  dev/tests/test_tool_loop_edges.py \
  dev/tests/test_outils_voix.py::test_artefact_whisper_sur_silence_ne_parvient_pas_au_brain \
  -q
```

```
.........................................................                [100%]
57 passed in 0.74s
```

Hallucinations connues rejetées, phrase normale passée, segment à
`no_speech_prob` haut rejeté, rejet absent hors mains libres. Un tour
écrit une ligne, deux tours en écrivent deux, fichier relisible, aucun
secret.

## Doutes

`parler_ecrit.py` charge le cerveau distant/local au boot : il doit
tourner **dans le conteneur**, là où le routeur écoute.

Le chemin hôte « produit » (`%LOCALAPPDATA%\hyper-ambient\conversations`)
n'est atteint que si le process tourne hors conteneur. Le host-agent
écrit via `/workspace/data/conversations`. À mentionner dans DONNEES.
