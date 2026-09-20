---
date: 2026-09-20
heure: ~11:05 Europe/Paris
type: taquet
lane: README-DEV
who: qwen
complexite: simple
statut: PRÊT À COLLER (3 trous signalés, aucun bloquant)
cibles: [README.md, README.en.md, .github/ISSUE_TEMPLATE]
sources: ["[[2026-09-19-CARTE-FIGEE]]", "[[2026-09-19-P0-1-SSD-E]]", "[[2026-09-19-ANNEXE-TECH-HYPER-AMBIANT]]"]
---

# TAQUET — README dev : pitch d'installation + harnais

**Cible de la lane.** Le texte que `README.md` (FR) et `README.en.md` (EN) doivent afficher en tête,
plus les 5 assertions de vérification. Un dev qui découvre Hyper Ambient 0.1 doit avoir une voix qui
répond en **moins de 20 minutes**, sans clé API, sans lire `ARCHITECTURE.md`, sans toucher au GPU à la main.

**Contrainte de vérité.** Chaque chiffre ci-dessous est lu dans le dépôt ou mesuré. Trois claims du
`README.md` actuel sont **faux** (voir §8) : ne pas les recopier.

## 1. Le pitch (8 lignes, à coller avant « Quick Start »)

```markdown
# Hyper Ambient 0.1 — voix locale sur Windows

Ça écoute, ça pense, ça répond à voix haute — sur ta machine. Zéro clé API pour démarrer.
Trois briques figées : **Granite 4.2 3B** (cerveau) · **Whisper large-v3** (oreille) ·
**Magpie 357M / Sofia** (voix). **7,3 Go de VRAM au repos sur 12 Go**, **~1,1 s** avant le premier son.

    make build && make up && make smoke     # 9 capacités sondées, mesures réelles affichées
    bash dev/scripts/relance_hostagent.sh   # la chaîne vocale sur :8001
    native\presence\hyper-ambient.bat       # la fenêtre : Appuie, parle, relâche

Changer de cerveau, de voix ou de langue est **un changement de config, pas de code**
(`.env.local` + `dev/scripts/carte_figee.env`). Interface 100 % clavier, contraste mesuré
**10,3:1**, transcription et réponse toujours affichées, français par défaut,
**anglais à un `HA_LANG=en`**.
Un bug, une envie : le bouton **« Un retour »** de Presence ouvre l'issue — 30 s.
```

## 2. Installation — la séquence qui marche (à recopier telle quelle)

```bash
git clone https://github.com/tbrignonen-ai/hyper-ambient && cd hyper-ambient
copy .env.example .env.local        # cp sous WSL. Tous les champs peuvent rester vides.
make build && make up && make shell # GPU réservé dans docker-compose — obligatoire
make models                         # ~5,9 Go : Granite + Whisper large-v3 + Magpie (voir §6)
```

Puis, dans le conteneur (`make shell`) :

```bash
make smoke                          # 9 capacités : gpu, binaires, ggml-cuda, EARS, TURN, MOUTH, acoustique, BRAIN
make llama                          # cerveau local :8090 — alias mother-local
bash dev/scripts/relance_hostagent.sh   # écho attendu : « carte figee: brain=llamacpp … mouth=magpie/Sofia/cuda »
exit
```

Côté hôte Windows (le son ne peut pas sortir du conteneur : Docker Desktop n'a pas d'ALSA) :

```bat
native\presence\hyper-ambient.bat
```

Le lanceur fait `start "" pythonw native\presence\app.py` : pas de terminal, `assurer_stdio()`
rattache stdout/stderr (et les fd C 1/2) à `%LOCALAPPDATA%\hyper-ambient\presence.log` — c'est le
correctif C13 de la « première requête dans le vide ». Repli de diagnostic : `python -u native\presence\app.py`.
Flags utiles : `--url` (défaut `ws://127.0.0.1:8001/hostagent`), `--device` / `--sortie` (indice PortAudio
ou fragment de nom), `--config` (chemin de config, pour tests et installations portables), `--onboarding`
(revoir l'assistant), `--sante <json>` (bandeau dégradé), `--sondes` (sonder les ponts en direct —
activé tout seul si `--sante` est absent).

**Pas de micro pour la première preuve ?** `python dev/scripts/verify_hostagent_loop.py` rejoue le
protocole WebSocket exact de `talk.py` (`hello/ready` → `invoke audio.capture` → `audio.render` jusqu'au
marqueur de fin) sur un WAV : `--audio data/in/question.wav` → `--out data/out/verify_loop_reponse.wav`,
verdict imprimé. Recette du pont audio, sans appareil d'enregistrement.

## 3. Harnais — ce qui prouve, en trois étages

| Étage | Commande | Ce que ça paie |
|---|---|---|
| Capacités | `make smoke` → `dev/scripts/smoke_test.py` | 9 lignes nommées : GPU/CUDA, `llama-server`, `whisper-cli`, ggml-CUDA vu, EARS faster-whisper, TURN silero-vad, MOUTH piper, acoustique R128, BRAIN joignable. **Mesures réelles imprimées**, puis « N ok, M failed, K skipped ». |
| Régression | `make test` → `python3 -m pytest dev/tests -v` (conteneur) | **84 fichiers / 1 077 fonctions** dans `dev/tests` (1 118 collectées au run du 19/09 : 1 105 passés, 11 ignorés, 2 échecs — les tests Presence natifs Windows, verts côté hôte). Gate, secours, transports, Presence/onboarding/overlay, chaîne d'outils, carte figée, i18n hors-ligne. Pas de suite séparée côté hôte : `native/` est testé depuis `dev/tests`. |
| Live | `dev/scripts/verify_hostagent_loop.py`, flags `--sante` / `--sondes` de Presence | boucle complète WebSocket→EARS→BRAIN→outils→MOUTH rejouée sans micro, bandeau dégradé et ponts agents sondés en direct. |

Relance officielle unique : `dev/scripts/relance_hostagent.sh` (tue l'ancien process, attend
l'écoute sur `:8001`, timeouts explicites). Comptes rendus de lane : `python dev/scripts/account.py board`.

## 4. Config modulaire — trois couches, aucun secret requis pour démarrer

1. **`.env.local`** (ignoré par git, monté **read-only** dans le conteneur) : secrets et URLs d'outils.
   **Un outil est absent du registre si sa clé est vide** — pas d'échec tardif en pleine conversation.
2. **`dev/scripts/carte_figee.env`** : la carte des modèles, sans secret. `CARTE_FIGEE=0` la désactive,
   `*_FORCE` (ex. `MOUTH_DEVICE_FORCE=cpu`, `EARS_DEVICE_FORCE=cpu`) écrase une clé sans retoucher le fichier.
3. **Les profils** (`dev/scripts/profiles/*.json`) : un profil par candidat TTS, mêmes questions, mêmes
   métriques → comparer des cerveaux est une boucle de harness, pas une après-midi de bricolage.

Les trois backends cerveau parlent `/v1/chat/completions` : `stepfun` | `llamacpp` | `openai` se choisit
dans `BRAIN_SERVICE`. EARS (`faster-whisper` | `qwen3` | `parakeet` | `whisper.cpp`), MOUTH
(`pocket` | `magpie` | `supertonic` | `piper` | `remote`) et la porte (`GATE_MODE=plan|ask|manual|auto|build|troubleshoot`)
suivent la même règle. `make demo-local` est le raccourci tout-en-un.

## 5. Accessibilité — déjà dans le code, à vendre sans honte

- **Tout est atteignable au clavier** : ordre de Tab construit depuis l'ordre de création, `takefocus=1`,
  `Enter` et `space` liés sur chaque bouton. Le focus est **rendu visible** (`_rendre_focus_visible`, élargisseur
  d'anneau + couleur) parce que le bouton `ttk` natif a un anneau de focus à épaisseur nulle — donc invisible.
- **Alternative texte permanente** : transcription, réponse, état d'appel distant et « premier son : … ms »
  restent affichés en texte ; le signal d'escalade n'est **pas seulement coloré** — l'éclair s'accompagne
  du libellé « Modèle local » / « Appel distant ». `Escape` ferme vraiment l'appli, « Masquer » ne fait
  qu'iconifier dans la barre des tâches. Contraste renforcé optionnel : `PALETTES_CONTRASTE` par état
  (`overlay.py`), choix persisté avec la langue et le raccourci PTT dans `%APPDATA%\hyper-ambient\presence.json`.
- **Contraste mesuré, pas déclaré** : `contraste_relatif()` dans `native/presence/sante.py` implémente la
  formule WCAG ; `#fff8e8` sur `#7a1212` = **10,32:1** (AA : 4,5 · AAA : 7). `dev/tests/test_presence_sante.py`
  appelle la fonction et assert `>= 4.5` au lieu de coder un nombre en dur — la preuve est exécutée, pas écrite.
- **PTT au clavier réellement câblé** : `Enter` **et** `space` en `KeyPress`/`KeyRelease` sur le bouton de
  parole (PTT maintenu au clavier), plus un raccourci global configurable `space` | `ctrl-space`.
- **PTT maintenu ou verrouillé**, et les modes texte/PTT des trois interfaces sont **persistés en JSON** pour
  les tests et les installations portables (`--config`).
- **Alerte sans jargon ni popup** : « Le pont vers Codex ne répond plus, je continue en local. »

Reste à prouver (ne pas l'écrire dans le README avant) : passage réel sous NVDA et navigation clavier
complète en situation. Marquer **[À PROUVER]**.

## 6. Carte des modèles + SSD `E:` — ne pas re-télécharger 5,9 Go

Artefact unique à embarquer, vérifié SHA256 avant/après sur `E:\HyperAmbient-models\`
(`nights/2026-09-19-P0-1-SSD-E.md`, dry-run Robocopy = 0 différence) :

| Brique | Fichier | Taille |
|---|---|---|
| Cerveau | `granite-4.2-3b-Q4_K_M.gguf` | 2,24 Go |
| Oreille | `faster-whisper-large-v3\` (cache HF complet, snapshots en liens reparse) | 3,09 Go |
| Voix | `magpie\magpie_tts_multilingual_357m.v2602.f16.gguf` + `nemo_nano_codec_…decoder.f16.gguf` | 449 Mo + 79 Mo |

Licences : Apache-2.0 · MIT · NVIDIA Open Model License (usage commercial autorisé) — c'est ce qui permet
de dire « local » sans zone grise. Replis documentés : NeoHorse-1-9B (cerveau), Parakeet-TDT-0.6B-v3 (oreille),
Supertonic F5 (voix, CPU, 0 VRAM).

**[À CÂBLER — 1 ligne]** `docker-compose.yml` ne monte que `./models` ; rien ne lit `E:\HyperAmbient-models`.
Pour le dev pressé, ajouter un volume `E:/HyperAmbient-models:/workspace/models-ssd:ro` et documenter
`MODEL=/workspace/models-ssd/granite-4.2-3b-Q4_K_M.gguf`. En attendant, `make models` reste le chemin officiel.
Lane SSD tenue par Codex ce matin : ne pas dupliquer.

## 7. Feedback GitHub — le bouton existe déjà, il faut le documenter

**C'est vendu, pas à faire.** `native/presence/onboarding.py` définit
`URL_FEEDBACK = "https://github.com/tbrignonen-ai/hyper-ambient/issues/new"` et `ouvrir_feedback()`
(l'argument `ouvrir` est injectable pour les tests, sans ouvrir de navigateur) ; `app.py` l'expose en
**bouton atteignable au clavier** « Un retour » / “Send feedback”, chaîne traduite FR+EN (`ui.feedback`,
`ui.feedback_url` dans `src/i18n/__init__.py`). Le dépôt public existe et la PR #1 y est référencée
(`nights/2026-09-17-CLOUD-TOOLLOOP-PR1.md`).

Ce que le bouton fait : **ouvrir une issue vierge dans le navigateur**. Rien n'est posté
programmatiquement, aucun token, aucun flag — donc rien à cacher derrière `GATE_MODE`. Trois pièces
manquent pour que le README puisse en dire plus :

1. **Aucun `.github/`** dans le dépôt → l'issue arrive sans formulaire. Créer `ISSUE_TEMPLATE/config.yml`
   + `feedback.yml` (attendu / obtenu / sortie de `make smoke` collée / langue / GPU) : un dev remplit un
   formulaire, il n'écrit pas un ticket.
2. **Aucune lecture en retour** : la fréquence de dépouillement des issues et la conservation des retours
   sont encore **[À PROUVER]** (`2026-09-19-ANNEXE-TECH-HYPER-AMBIANT.md`, [À PROUVER] n°5). `prompt.md`
   décrit une vérification quotidienne Camunda des issues/PR : c'est une étude de cas BPMN, pas du code.
3. **Étiquettes** `feedback`, `voice`, `install` à créer (`gh label create`) — hors README.

Et une règle à écrire noir sur blanc dans le README : **le retour est déclenché par l'humain**, jamais par
le modèle ; la porte `GATE_MODE` reste le seul chemin qui autorise une écriture externe.

**Ne pas dupliquer** : la lane Cursor PRODUIT de ce matin a déjà ouvert `dev/tests/test_taquet_produit.py`
(non versionné) qui assert l'URL de feedback, les chaînes EN, la persistance du contraste et le stdio de
`pythonw`. Ces assertions recoupent §5 et §7 : coller le README sans les casser.

## 8. Ce qu'il faut corriger en écrivant le README (7 points, vérifiés dans le code)

| # | Faux aujourd'hui | Vérité du dépôt |
|---|---|---|
| 1 | `README.md` : « `make smoke` → **9/9 ✓** » (3 fois) | `smoke_test.py` sonde bien **9 capacités**, mais n'affiche **jamais** « 9/9 » : il imprime une ligne par capacité puis « N ok, M failed, K skipped ». Surtout, 2 de ces 9 lignes sondent des **héritages** — `MOUTH piper` (le repli, pas Magpie/Sofia) et `whisper-cli` (le binaire, pas l'oreille figée). « 9/9 » ne prouve donc **pas** la carte figée. |
| 2 | `README.md` (2026-08-21) : MOUTH = Pocket TTS `estelle`, BRAIN = LFM2.5-2.6B, escalade MiniMax-M3, « 500 ms round-trip », « 96,01 % » | Carte figée 19/09 : Granite 4.2 3B · Whisper large-v3 · Magpie/Sofia. Mesures live : oreille 0,45–0,7 s, 1er jeton 25–70 ms, **premier son ~1,1 s** (3,2–4,8 s sur phrase longue). |
| 3 | `README.md` : « `Storage`: 25+ GB for models » + commentaire `make models` « VAD + Piper FR voice + whisper turbo (~1.2 GB) » | `fetch_models.sh core` télécharge **~5,9 Go** (Granite + large-v3 + Magpie) et n'accepte que `{core|brain|all}` — les 16 profils TTS ne passent **pas** par `make`, ils se téléchargent dans le venv du banc. Commentaire à réécrire. |
| 4 | Absent du `README.md` FR | `HA_LANG=en` / `HYPER_AMBIENT_LANG=en` : le FR+EN est **déjà écrit** (`src/i18n/__init__.py`, ~250 clés) mais le README principal ne le dit pas. Le FR+EN est aussi un critère éliminatoire de la sélection des modèles → à vendre deux fois. |
| 5 | Absents du `README.md` FR | L'accessibilité de Presence (§5), la relance unique `relance_hostagent.sh` (§3) et le bouton « Un retour » (§7) ne sont nulle part — trois des quatre arguments qui différencient ce projet d'un démo Gradio. |
| 6 | Détail | `Makefile` : `.PHONY` (ligne 1) omet `gpu` et `demo-local`, qui existent comme cibles (l.26 et l.48). |
| 7 | Piège réel au premier `make demo` | `.env.example` **n'est pas à jour de la carte figée** : `BRAIN_SERVICE=stepfun` (clé requise), `EARS=qwen3/0.6B`, `MOUTH=pocket/estelle`, `MODEL=MiniCPM5-2B`. La carte n'est appliquée qu'au boot du host-agent (`serve_hostagent` + `relance_hostagent.sh`), donc `copy .env.example .env.local` → `make demo` part sur un backend sans clé et **échoue au premier essai**. Aligner `.env.example` sur `carte_figee.env`, ou écrire dans le README : « pour la voix, passe par `relance_hostagent.sh`, pas par `make demo` ». |

## 9. EN mirror (à coller dans `README.en.md`)

> **Hyper Ambient 0.1 — a local voice on Windows.** It listens, thinks and answers out loud on your
> machine, with no API key to get started. Frozen stack: IBM Granite 4.2 3B · Whisper large-v3 ·
> Magpie 357M (Sofia). **7.3 GB VRAM idle out of 12**, **~1.1 s** to first sound.
> `make build && make up && make smoke` (5 real probes, printed measurements) →
> `bash dev/scripts/relance_hostagent.sh` → `native\presence\hyper-ambient.bat`.
> Swapping brain, voice or language is a **config change, not a code change**
> (`.env.local` + `dev/scripts/carte_figee.env`, override with `*_FORCE`).
> Fully keyboard operable, focus drawn explicitly, contrast **measured at 10.3:1**, transcript and answer
> always on screen, French by default, **English with `HA_LANG=en`**.
> Found a bug? [Open an issue](https://github.com/tbrignonen-ai/hyper-ambient/issues/new) — 30 seconds.

Note FR/EN : les deux README doivent garder les **mêmes** chiffres et les mêmes `[À CÂBLER]`. Un
`README.md` anglais daté du 21/08 et un `README.en.md` daté du 20/09 racontent deux produits différents —
c'est le premier trou de confiance pour un dev qui lit.

## 10. Critères d'acceptation de la lane

- [ ] §1 collé en tête de `README.md` (FR) **et** l'équivalent §9 dans `README.en.md`.
- [ ] Aucune occurrence de « 9/9 » ; le chiffre affiché est celui de la sortie réelle.
- [ ] Les 3 claims faux du §8 disparus ; dates d'en-tête mises à jour (même date dans les deux fichiers).
- [ ] Section « Feedback » du README = **le bouton « Un retour » qui existe** (§7), rien d'autre : pas de
      formulaire GitHub, pas d'envoi automatique, pas de `make feedback` tant que les 3 pièces ne sont pas là.
- [ ] Aucun flag Presence inventé : `app.py` n'accepte que `--url`, `--device`, `--sortie`, `--config`,
      `--onboarding`, `--sante`, `--sondes`. Tout ce qui dépasse cette liste doit être relu dans le code.
- [ ] `[À CÂBLER]` §6 et §7 ouverts en issues (2 tickets), pas refermés dans le doc.
- [ ] `make smoke` et `python3 -m pytest dev/tests -q` relancés après modification, sortie collée dans l'OUT.

## 11. Hors scope de cette lane

`workers/` (camunda-operate) n'est pas mentionné dans le README — le faire est une décision séparée.
Pas de refactor des cibles Makefile (sauf `.PHONY`, cosmétique), pas de touche aux modèles ni à `E:`,
aucun secret dans le doc. La lane ANNEXE (Claude) garde la main sur le texte de soutenance : ce taquet
alimente le README, pas l'annexe.

---

**OUT** : ce fichier. **EXIT** : `nights/2026-09-20-TAQUET-README-DEV-EXIT.txt` (0 = doc écrit et vérifié
contre le dépôt). Notification : lane simple → OC + ponts, pas d'OG.
