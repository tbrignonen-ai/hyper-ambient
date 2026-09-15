---
date: 2026-09-13
heure: ~17:45 Europe/Paris
type: reprise-lead
auteur: Claude (Opus 5, lead technique)
related:
  - "[[2026-09-13-ASSIGN-CURSOR-VOIX-10]]"
  - "[[2026-09-13-CURSOR-TTS-POCKET]]"
  - "[[2026-09-13-CODEX-VOIX-REGRESSION]]"
  - "[[2026-09-13-INTENT-ONBOARDING-UX]]"
  - "[[2026-09-13-DECISION-DROP-WORLD]]"
---

# Claude reprend le siège — plan court

## Constat à la reprise (vérifié, pas recopié)

| Élément | État mesuré ~17:45 |
|---|---|
| `mother-core-dev` | Up ; un seul `serve_hostagent.py` (PID 8400) |
| MOUTH | Pocket TTS `french_24l` / `estelle` / `aurora`, CPU |
| EARS | Qwen3-ASR 0.6B q4 CUDA, hook dtype en place |
| VRAM | 6326 / 12282 MiB — dans l'enveloppe 8–10 Go |
| Chantier 10 voix | Cursor lancé 17:41 ; `data/out/voix-10-samples/` pas encore créé |
| Handover Codex | écrit (`HANDOVER-CLAUDE.md`), lu, cohérent avec ce constat |
| World | **DROPPED** — plus aucune ressource dessus |
| Git | `nuit/2026-08-27`, 21 fichiers modifiés + ~25 non suivis, rien commité aujourd'hui |

## Inventaire voix disponible sur disque (sert à juger le pack de Cursor)

- **Pocket TTS `french_24l`** : 13 embeddings — alba, anna, azelma, caro_davy, cosette,
  eponine, estelle, eve, fantine, jane, lola, mary, vera. Flux continu, CPU, 0 VRAM.
- **Piper natif FR** : siwis, tom, upmc (jessica/pierre), mls. Bloc par phrase, CPU.
- **Supertonic 3** : styles F1–F5 / M1–M5 (ONNX, CPU).
- **Qwen3-TTS 1.7B Base GGUF** + `speaker_fr.wav` (clonage) — lourd, hors chemin live.
- `ffmpeg` + `pydub` présents dans le conteneur → encodage MP3 sans rien installer.

## Tension à garder en tête pour le choix

- 8 sept : Thomas a entendu un accent britannique sur Pocket `eponine` → bascule Piper.
- 13 sept après-midi : Thomas rejette les voix Piper (siwis/upmc/tom) → retour Pocket `estelle`.
- Donc ni « natif Piper » ni « Pocket » ne gagne d'office : **l'oreille de Thomas tranche
  sur un même texte long**, c'est exactement ce que le pack de 10 permet.
- Le texte long est un bon révélateur d'un défaut connu : Pocket passe `max_tokens=50`
  (`src/mouth/pocket_tts.py:51`), la bibliothèque découpe et remet la prosodie à zéro à
  chaque morceau. Si Thomas entend des coutures sur les samples Pocket, c'est la piste n°1.
  **Vérifié dans la lib (`pocket_tts/models/tts_model.py:666`, `text_chunking.py:110`)** :
  découpe aux fins de phrase, puis **aux virgules** si une phrase dépasse 50 tokens ; chaque
  morceau repart de l'état du prompt vocal (`copy_state=True`, pas de teacher forcing).
  La 2e phrase du script long (~60 mots) sera donc découpée aux virgules → c'est là qu'il
  faut écouter. Levier bon marché à tester si coutures : `max_tokens` plus haut (ex. 120),
  mesuré à l'oreille et en RTF, avant tout travail sur le chaînage d'état.

## Plan jusqu'à 18h

1. **17:45–18:00 — superviser Cursor VOIX-10.** Contrôler : 10 MP3 réels, > 20 s, même
   script, timbres différents (pas 10 fois Pocket), `INDEX.md` rempli, host-agent Pocket
   estelle toujours seul et vivant à la fin (piège : double chargement Pocket dans le
   plafond 8 Go du conteneur).
2. **18:00 — wrap.** Ce qui est démontrable : boucle vocale option 2 (ASR fixé, Pocket
   estelle live, VRAM ~6,3 Go) + pack d'écoute. Ce qui est racontable : onboarding (intent
   seulement), world abandonné.
3. **Pas de commit sans Thomas.** Le working tree du jour reste à solder en commits
   thématiques quand il valide.

## Contrôle du pack 10 voix (Claude, 17:58)

Livré par Cursor à 17:55 dans `data/out/voix-10-samples/` (`INDEX.md`, `run.log`, script
`dev/scripts/_voix_10_samples.py`).

| Contrôle | Résultat |
|---|---|
| 10 MP3 présents | oui (ffprobe) |
| Durée > 20 s | oui, 32,3 s → 46,2 s |
| Même texte | oui — `_voix_10_script.txt` identique à `SCRIPT-VOIX-LONG.txt` (diff) |
| Moteurs distincts | 5 : Pocket ×2, Piper ×4, Supertonic ×2, Qwen3-TTS clone ×1, MMS-TTS ×1 |
| Host-agent restauré | oui, PID 9841, `MOUTH_BACKEND=pocket` / `estelle` / `aurora` / cpu |
| VRAM après | 6098 MiB |

Écoute proposée à Thomas, dans l'ordre :

| # | Voix | À écouter pour |
|---|---|---|
| 01 | Pocket estelle | référence live actuelle |
| 02 | Pocket cosette | autre timbre Pocket |
| 03–06 | Piper siwis / upmc / mls / tom | déjà jugées mauvaises cet après-midi, gardées pour comparaison sur texte long |
| 07–08 | Supertonic F5 / F1 | moteur nouveau, CPU, 44,1 kHz |
| 09 | Qwen3-TTS clone | clone de `aurora_prompt_6s.wav` (réf. « Aura Ray », 29 août) |
| 10 | MMS-TTS fra | VITS Meta, moteur distinct |

Réserves du lead :
- **09 est un clone d'une voix réelle** (extrait YouTube). Bon pour la cible esthétique,
  mais à ne pas figer pour la soutenance publique sans droit d'usage de la voix
  d'origine. Si Thomas le préfère : s'en servir comme cible pour choisir un timbre proche
  parmi les voix libres. Qwen3-TTS a tourné sur CUDA (bf16), ~2,8–16 s par phrase : hors
  chemin temps réel en l'état.
- Piper `MOUTH_VOICE` pointe encore sur tom dans l'env du host-agent ; sans effet tant que
  `MOUTH_BACKEND=pocket`, à nettoyer au gel.

## Après 18h — suite

### A. Figer la voix (dès que Thomas a écouté)
1. Thomas donne 1 numéro (ou 2 finalistes).
2. Si finaliste = Pocket : régénérer le **même texte long en live** (via host-agent, pas
   hors-ligne) pour vérifier qu'il n'y a pas de coutures ; si coutures → traiter
   `max_tokens` / jointure de morceaux (TDD, test de continuité sur un texte > 50 tokens).
3. Si finaliste = Piper ou Supertonic : mesurer le délai avant premier son sur une phrase
   longue (Piper émet par phrase entière) avant de figer.
4. Figer dans `.env.local` + défaut `relancer_routeur.sh` + `serve_hostagent.py`, relancer
   sans `FORCE`, une recette audio de bout en bout, puis nettoyer `models/` des rejets
   (garder un fallback Piper siwis).

### B. Qualité des réponses (grief « pourri » de 17:05, non traité)
Reco Codex vérifiable et peu risquée : température 0,2 sur le canal distant, consigne de
rigueur courte dans le prompt, une seule amorce. À faire en TDD sur `src/brain/router.py`
après le gel voix — une chose à la fois pour que l'oreille de Thomas sache ce qui a changé.

### C. Hachure côté Windows (hypothèse Codex, confiance moyenne)
Instrumenter le client `native/presence/app.py` (underflow, espacement réel des paquets,
rééchantillonnage implicite 16 k → 44,1 k MME) **avant** toute réécriture du transport.

### D. Onboarding (intent locké, pas encore de spec)
Intent : le modèle local se charge et guide l'onboarding ; fenêtre app de configuration
qui se masque ; PTT + raccourci clavier ; accessibilité = contrainte produit.
Proposition de séquencement (à valider Thomas, puis `/speckit.specify`) :
1. **PTT + raccourci global** d'abord — c'est la brique d'accessibilité et elle se voit le 25.
2. **Parcours onboarding parlé minimal** : 3 étapes guidées par le réflexe local (choix de
   la voix parmi les finalistes → test micro → premier ordre), config écrite puis fenêtre
   masquée.
3. Visuel distant (image toutes les ~2 min) = option avancée, après le 25 si pas le temps.

## Garde-fous rappelés
`docker start` jamais `compose up`/recreate · pas de push · hermes/OpenClaw éteints ·
pas deux agents sur les mêmes fichiers (Cursor possède `data/out/voix-10-samples/` et son
script de génération pendant le chantier).
