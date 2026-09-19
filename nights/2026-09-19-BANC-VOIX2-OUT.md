---
date: 2026-09-19
type: out
cible: banc-voix-2
---

# BANC VOIX 2 — OUT

Phrase imposée (non répétée dans les WAV anonymisés au-delà de l'audio) : identique à la dégustation 1.

## Référence clone (siwis)

- Modèle Piper : `/workspace/models/piper/fr_FR-siwis-medium.onnx`
- Texte : « Le vent glisse le long de la rue déserte, et les lampadaires éclairent à peine le trottoir humide. Un oiseau traverse le ciel gris. »
- Durée brute : 7.755 s · 22050 Hz
- Copie : `nights/degustation-19/.sources/siwis_ref.wav` + `siwis_ref.txt`
- Débit Piper : `--length-scale 1.111` (≈ 0,9)

## Tableau (lettres d'anonymisation absentes)

| Candidat | Voie | Device | Temps synthèse | VRAM max | Windows natif | Statut |
|---|---|---|---:|---:|---|---|
| neuphonic/neutts-air (q4 GGUF) | — | — | — | — | — | **échec** |
| tencent/AuK-Flash | — | — | — | — | — | **échec** |
| Edge0/audio8-TTS-0.1B-ONNX-INT8 | clone siwis | CPU | 132.3 s | 0 MiB | oui | OK |
| nvidia/magpie_tts_multilingual_357m | Aria (feminine, --voice Aria --language fr) | CPU | 7.4 s | 0 MiB | oui | OK |
| Serveurperso/OmniVoice-GGUF | clone siwis | CPU | 74.1 s | 0 MiB | oui | OK |
| référence F5 | F5 | préexistant | — | — | oui | OK |

## Échecs d'installation / inférence

### neuphonic/neutts-air (q4 GGUF)

Cause : Echec double : (1) neuphonic/neutts-air et neuphonic/neutts-air-q4-gguf sont gated=auto (401 sans jeton ; HF_TOKEN absent de l'environnement du conteneur, len=0). (2) pip install 'neutts[all]' tire torch>=2.8 (roue 2.14) + llama-cpp-python source (75 Mo) dans un cgroup memoire.max=8 Go deja occupe par le host-agent ; l'install a ete arretee avant OOM. Backbone Air = anglais (FR officiel = neutts-nano-french, hors brief).

### tencent/AuK-Flash

Cause : inférence impossible dans le cgroup 8 Go (memory.max=8589934592, current=7708479488) : AuK-Flash exige l'encodeur Qwen/Qwen2.5-Omni-3B (~6 Go fp16) + DiT, alors que le host-agent doit rester chargé. Poids Flash téléchargés ou tentés ; encodeur 3B non téléchargé pour ne pas saturer le disque/RAM. Langues déclarées zh/en (pas FR natif) — clonage siwis prévu mais non exécuté.

## Notes

- Conteneur `mother-core-dev`, cgroup mémoire 8 Go, host-agent laissé intact (pas de relance `:8090`).
- Un venv / préfixe par candidat sous `/workspace/models/tts-bench/<nom>/`. `asr-bench` non touché.
- WAV livrés : mono 16-bit, RMS cible −20 dBFS.
- OmniVoice-GGUF : licence **CC-BY-NC-4.0** (non commerciale).
- NeuTTS-Air est un backbone **anglais** (FR = nano-french, hors brief) ; clonage siwis prévu.
- Magpie : voix féminine intégrée Aria (idx 0), français natif, pas de clonage (retiré par NVIDIA).
- Correspondance lettres ↔ modèles : `nights/degustation-19/voix2/.carte-secrete.json` (non recopiée ici).
- Fichiers WAV produits : 4.
- Horodatage pack : 2026-09-19T13:24:50Z

