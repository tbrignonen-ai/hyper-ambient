---
date: 2026-09-14
type: rapport
auteur: Claude (Opus 5)
ordre: nights/2026-09-14-ORDRE-CLAUDE-VOIX-V2.md
statut: EN COURS
---
# CLAUDE — voix v2, 10 MP3 (rapport)

_Brouillon en cours de séance ; mis à jour à la clôture._

## Résumé

- Paquet : `data/out/voix-10-samples-v2/` — index `INDEX.md`.
- Contrôle automatique de chaque MP3 : faster-whisper large-v3-turbo (langue, recouvrement avec le script, derniers mots, fuite du prompt anglais). **Ce n'est pas une écoute humaine** : le jugement à l'oreille reste à Thomas.

## Tableau par slot

Contrôle auto : Whisper large-v3-turbo sur le MP3 livré (langue détectée, part des mots du script retrouvés, derniers mots entendus, fuite du prompt anglais). « Structure, » en tête de phrase et « Sous-titrage Société Radio-Canada » en fin sont des hallucinations classiques de Whisper sur les silences, pas du contenu audio — à confirmer à l'oreille.

| Slot | Modèle / révision | Licence | Commande | Durée | SR | Taille | Synthèse | VRAM max | Qualité FR (auto) | Fidélité Aura | Anomalie |
|---|---|---|---|---:|---:|---:|---:|---:|---|---|---|
| 01 | `openbmb/VoxCPM2@32279ef`, voxcpm 2.0.3 | Apache-2.0 | `--job voxcpm2` (venv principal) | 54,6 s | 48 000 | 596 Ko | 175,6 s (chargement inclus) | 5 961 Mio | FR, 98 % des mots, fin entendue | à juger à l'oreille | 3 OOM au chargement avant correctif bf16 ; `seed=` refusé par l'API PyPI |
| 02 | `neuphonic/neutts-nano-french@c04ee51` | other (Neuphonic) | — | — | — | — | — | — | — | — | **Non livré** : dépôt gated (401), aucun jeton HF |
| 03 | `Edge0/Audio8-TTS-Preview-0.6b@f07040f` | Apache-2.0 | `--job audio8` (+ `PYTHONPATH` Audio8_TTS) | 45,6 s | 44 100 | 522 Ko | ~150 s (7 fragments < 150 car.) | voir meta | FR (p = 1,0), 99 % des mots, fin entendue, transcription propre | à juger à l'oreille | aucune |
| 05 | `krmkayabasi/Anka-TTS@f1ce92d` (livré le 13/09) | CC-BY-NC-4.0 | non relancé (ordre) | 41,9 s | 24 000 | 403 Ko | 159,2 s | — | **Échec auto** : début détecté anglais, 48 % des mots, fin inintelligible (« Dula Dernire ») | à juger à l'oreille | Ne passe pas les critères bloquants de la section 3 ; non régénéré conformément à l'ordre |
| 10b | `ResembleAI/chatterbox@5bb1f6e` multilingual V3 | MIT | non relancé (ordre) | 37,8 s | 24 000 | 353 Ko | 689,4 s | — | FR, 99 % des mots, fin entendue | à juger à l'oreille | **Repli hors cutoff** : poids du 2026-06-10, antérieurs au 13 juillet |

(slots 04, 06, 07, 08, 09 : à compléter)

## Incidents et corrections

1. **Conteneur plafonné à 8 Go de RAM (cgroup)** — trois OOM kills silencieux (code 137) au chargement de VoxCPM2. Cause : la bibliothèque construit le modèle 2B en fp32 sur CPU (~8 Go) avant de le passer en bf16. Correction dans le job : construction directe en bf16 sur GPU (`torch.set_default_dtype` + `torch.device`). Même correctif appliqué à dots.tts (cœur 2B), avec vocodeur et encodeur de locuteur rechargés en fp32. Raon : `torch.load(mmap=True)` sur le checkpoint de 16,7 Go.
2. **Téléchargements xet gourmands** — le client xet de `hf` monte à 2,3 Go de RSS par dépôt ; relancés en HTTP simple (`HF_HUB_DISABLE_XET=1`), ~150 Mo chacun. Effet de bord : le téléchargement partiel de Raon (9 Go) a été perdu à l'arrêt du process xet.
3. **`pkill -f` / `pgrep -f` qui se trouvent eux-mêmes** — deux fois, le motif figurait dans la ligne de commande du shell appelant (arrêt raté des téléchargements, attente Audio8 infinie). Remplacé par des PID explicites et le motif `[x]yz`.
4. **API installée ≠ README** — `voxcpm` 2.0.3 (PyPI) refuse `seed=` ; graine fixée par `torch.manual_seed(42)` avant chaque phrase.
5. **Dépendances incompatibles** — dots.tts exige torch ≥ 2.8, FireRedTTS3 épingle torch 2.8 / transformers 5.6.2 : les monter dans le venv partagé (torch 2.6) aurait cassé VoxCPM2 / Audio8 / Magpie. Venv isolé `models/tts-v2-firered-venv` (FireRed + dots + Raon). FireRedTTS3 n'a ni `setup.py` ni `pyproject` : `pip install -e` impossible, requirements sans `flash_attn`, code par `PYTHONPATH`. Téléchargement torch 2.8 depuis PyPI bloqué à 87 ko/s → index `download.pytorch.org/whl/cu128`.
6. **IndexTTS** — la branche `indextts-2.5` n'existe pas ; clone du tag `v2.5.0`. Le venv uv n'a pas scipy (requis par le DSP `aurora`) : ajouté après `uv sync`.
8. **PyPI bridé** — `files.pythonhosted.org` plafonnait à ~150 ko/s (conteneur et hôte), alors que Hugging Face et `download.pytorch.org` débitaient normalement : `uv sync` d'IndexTTS, venv torch 2.8 et NeMo étaient à l'arrêt de fait. Mesure faite, le miroir `mirrors.aliyun.com/pypi` sortait ~1,2 Mo/s : les trois installations ont été relancées dessus (torch 2.8 toujours depuis l'index PyTorch cu128).
9. **Raon non installable en editable** — le `pyproject.toml` du dépôt officiel déclare `build-backend = "setuptools.backends._legacy:_Backend"`, module qui n'existe pas : `pip/uv install -e` échoue. Dépendances d'exécution installées explicitement, code chargé via `PYTHONPATH=.../Raon-OpenTTS/src`. Le driver est aligné.
10. **NeMo : `pyopenjtalk` ne compile pas** — l'extra `nemo_toolkit[tts]` tire `pyopenjtalk` (japonais uniquement), livré en sources, dont la construction échoue. Repli : `nemo_toolkit==3.0.0` sans extra + dépendances TTS utiles au français, sans `pyopenjtalk` (`logs/tts-v2/nemo_repli.sh`). `nemo_text_processing` (et donc pynini + compilation `cdifflib`) retiré à son tour : Magpie tourne avec `apply_TN=False`, le script n'ayant ni chiffre ni abréviation. Dernier manque : NeMo 3.0.0 importe `nv_one_logger` sans condition depuis son cœur (`nemo.lightning.one_logger_callback`), paquets déclarés seulement dans les extras `core`/`lightning` — ajoutés explicitement. Au passage, `facebook/w2v-bert-2.0` contient deux fois les poids (`model.safetensors` et `conformer_shaw.pt`, 2,3 Go chacun) : téléchargement restreint aux safetensors, seuls chargés par transformers.
11. **IndexTTS télécharge ses modèles auxiliaires au premier chargement** (`ensure_models_available` : `facebook/w2v-bert-2.0`, semantic codec `amphion/MaskGCT`, `funasr/campplus`, `nvidia/bigvgan_v2_22khz_80band_256x`). Préchargés dans `models/tts-v2/IndexTTS-2.5/hf_cache/` avant le job GPU, pour ne pas bloquer la file ; noyau CUDA BigVGAN non compilé (`use_cuda_kernel=False`). FireRedTTS3 lancé avec `use_fasttext=False` (langue imposée `French`).
12. **Verrou du cache uv** — deux processus uv partagent `models/uv-cache` (`uv sync` d'IndexTTS et l'installation du venv torch 2.8) et visent la même entrée (`nvidia-cuda-nvrtc-cu12`) : le second a échoué sur un *lock timeout*. Premier diagnostic erroné de ma part (lu comme un timeout réseau sur une fin de log tronquée, relance inutile) ; relancé avec `UV_LOCK_TIMEOUT=1800`. Ce n'était pas suffisant : vérification des descripteurs ouverts (`/proc/PID/fd`), les deux processus uv tenaient chacun une partie des verrous des roues NVIDIA (cublas, cudnn, cufft, cusolver, cusparse, cusparselt, nccl, triton) et attendaient l'autre — **interblocage**, 0 E/S, tous deux endormis. Correction de fond : sérialisation. `uv sync` d'IndexTTS arrêté (~18:11), venv torch 2.8 laissé finir (il débloque dots et FireRed), `uv sync` relancé automatiquement ensuite sur cache chaud.
13. **Raon mis en pause (choix délibéré, ~17:57)** — 2,3 Go reçus sur 16,7 Go à 3-5 Mo/s : impossible avant 19:00. Le débit total plafonnant à ~20 Mo/s, son flux ralentissait FireRed et les trois installations qui bloquent chacune un slot. Téléchargement arrêté, fichier partiel conservé pour reprise ultérieure.
7. **NeuTTS (slot 02) bloqué** — `neuphonic/neutts-nano-french`, ses GGUF et `neuphonic/neucodec` sont des dépôts **gated** (401 sans jeton). Aucun jeton Hugging Face dans le conteneur ni sur l'hôte. Accès « auto » : il suffit d'accepter la licence sur la page du modèle avec un compte HF et de fournir un jeton.
