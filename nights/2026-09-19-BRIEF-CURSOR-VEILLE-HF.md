---
date: 2026-09-19
type: brief
cible: Cursor (Grok 4.6)
auteur: Claude (MOTHER-PLAN-19)
---

# BRIEF Cursor — V1 Veille Hugging Face par API (pas par recherche web)

Objectif : figer les modèles LOCAUX de MOTHER (oreille, cerveau, voix) à partir des vraies nouveautés.
Méthode imposée : **API publique Hugging Face** (`https://huggingface.co/api/models`), sans jeton. Pas de moteur de recherche, pas de souvenir de modèle.

## Livrables
1. `dev/scripts/veille_hf.py` — stdlib uniquement (urllib, json), relançable chaque nuit.
   Test : `dev/tests/test_veille_hf.py` sur les fonctions de filtre/tri (données JSON fictives, sans réseau). Test rouge vu puis vert.
2. `nights/2026-09-19-VEILLE-HF.md` — produit par le script, puis complété à la main par toi (colonne « avis »).

## Balayage (paramètres API utiles)
`sort=trendingScore` et aussi `sort=createdAt` ; `limit=100` ; `expand[]=createdAt,lastModified,likes,downloads,library_name,tags,safetensors,gguf,cardData`
(si un `expand` groupé échoue, répéter `expand[]=` par champ).

| Catégorie | Filtres | Contraintes MOTHER |
|---|---|---|
| **ASR (oreille)** | `pipeline_tag=automatic-speech-recognition` ; avec ET sans `language=fr` | français obligatoire ; ≤ 2 Md param. ; streaming = bonus |
| **TTS (voix)** | `pipeline_tag=text-to-speech` ; avec ET sans `language=fr` | français obligatoire ; voix féminine grave/lente possible ; CPU ou ≤ 2 Go VRAM |
| **LLM (cerveau)** | `pipeline_tag=text-generation` + `library=gguf` ; et modèles de base récents | doit tenir avec oreille+voix dans **10 Go VRAM total** → poids Q4 ≲ 6 Go (dense ≲ 9 Md, ou MoE dont le Q4 ≲ 6 Go) ; français correct ; appel d'outils = bonus |

Fenêtre : créés ou modifiés depuis **120 jours** (priorité aux 30 derniers jours), + les références actuelles pour comparer :
Whisper large-v3-turbo, Qwen3-ASR, Parakeet TDT 0.6B v3, Kyutai stt-1b-en_fr ; Supertonic-3, Piper fr ; Luciole-8B, Ministral-3-8B, Qwen3.5-4B.

## Pour chaque candidat retenu (top 15 par catégorie)
id · date · likes · téléchargements · taille (param. via `safetensors.total` ou `gguf.total`) · licence (`cardData.license`) ·
formats dispo (gguf / onnx / ctranslate2 / safetensors) · **preuve du français** (tag `fr` ou mention dans la fiche — citer) ·
**indice Windows natif** (gguf/onnx/ctranslate2 = oui probable ; NeMo/Rust seul = à vérifier) · lien.
Puis **top 5 recommandé par catégorie** avec une ligne de justification. Marquer [À VÉRIFIER] tout ce que l'API ne prouve pas.

## Interdits
Aucun téléchargement de poids · ne pas lire `.env*` · aucune dépendance pip · ne modifier aucun autre fichier · pas de git.
Réponds seulement `OK` quand les deux fichiers existent.
