---
date: 2026-09-13
type: out
auteur: Cursor (grok-4.6-xhigh)
cible: Thomas + OC + Claude
statut: wan2.7-image identifié (API DashScope, 0 VRAM) ; 2 PNG présence livrés en repli faute de clé
related:
  - "[[2026-09-13-ASSIGN-CURSOR-WAN27]]"
  - "[[2026-09-13-LOCK-WAN27-IMAGE]]"
  - "[[2026-09-13-DECISION-DROP-WORLD]]"
---

# Cursor — images wan2.7 (13 sept)

Assign : trouver wan2.7-image qui **FITTE**, 2 samples présence visuelle douce, OUT lancer / VRAM / limites.

## Verdict

**Choix : remote `wan2.7-image` (Alibaba Cloud Model Studio / DashScope).** C’est le lock. Ça FITTE : **0 VRAM locale**, hors enveloppe 8–10 Go. Pas day-1 Crazy.

**Checkpoint local : introuvable.** Hub HF, requête `wan2.7-image` / `Wan2.7` : tableau vide (13 sept). Org `Wan-AI` s’arrête à Wan 2.1 / 2.2 (+ Animate-2, Dancer). Pas de `Wan-AI/Wan2.7-*`. Le 2.7 image n’existe que comme ID d’API.

**2 PNG livrés** dans `data/out/images-wan27/`. **Ce ne sont pas des wan2.7.** `DASHSCOPE_API_KEY` absent (`.env.local` et env docker). Le lanceur s’arrête en exit 2. Les PNG sont un **repli de style** (Cursor GenerateImage, 1280×720) pour que le dossier ne soit pas vide. Relancer le script avec la clé **écrase** ces fichiers par le vrai modèle.

## Preuves

HF, 13 sept :

```
curl -s "https://huggingface.co/api/models?search=wan2.7-image&limit=20"
→ []
```

Doc officielle (modèle, payload, 1K/2K, thinking_mode) :

https://help.aliyun.com/en/model-studio/wan-image-generation-and-editing-api-reference

Prix (page Model Studio, 13 sept) :

| Région | `wan2.7-image` | `wan2.7-image-pro` | Quota gratuit |
|---|---|---|---|
| Beijing | 0,20 CNY / image | 0,50 CNY / image | 50 images / 90 jours |
| Singapore | 0,224826 CNY / image | 0,562065 CNY / image | aucun |

Lanceur, hôte **et** `mother-core-dev` :

```
STOP: DASHSCOPE_API_KEY absent. wan2.7-image est une API DashScope, pas un checkpoint local.
exit 2
```

PNG livrés (signature `89 50 4E 47`, IHDR 1280×720) :

| Fichier | Octets | Moteur |
|---|---:|---|
| `data/out/images-wan27/01-presence-lampe.png` | 663189 | Cursor GenerateImage (repli) |
| `data/out/images-wan27/02-presence-orbe.png` | 738830 | Cursor GenerateImage (repli) |

VRAM pendant ce split (`nvidia-smi`) : **3067 / 12282 MiB**. La génération image n’a rien chargé sur la 4070. Le 3,0 Go déjà là n’est pas wan2.7.

## Comment lancer (vrai wan2.7)

1. Clé Model Studio : https://help.aliyun.com/en/model-studio/get-api-key  
   Beijing et Singapore **ne se mélangent pas** (clé + host distincts).

2. Dans `.env.local` (déjà documenté dans `.env.example`) :

```
DASHSCOPE_API_KEY=sk-...
DASHSCOPE_REGION=singapore
```

Europe : `singapore` (host `dashscope-intl.aliyuncs.com`). Pour le quota gratuit 50 images : compte **Beijing** + `DASHSCOPE_REGION=beijing`.

3. Générer (écrase les 2 PNG du dossier) :

```powershell
docker exec -e PYTHONUNBUFFERED=1 -w /workspace mother-core-dev python /workspace/dev/scripts/gen_wan27_images.py
```

Hôte, même fichier : `python dev/scripts/gen_wan27_images.py`

Overrides : `WAN27_MODEL=wan2.7-image` (défaut, plus rapide / moins cher que `-pro`), `WAN27_SIZE=1280*720`, `WAN27_THINKING=1`.

Le script POST sur `/api/v1/services/aigc/multimodal-generation/generation`, `n=1`, `watermark=false`, puis **télécharge** les URL (valables 24 h).

## VRAM / limites

| | |
|---|---|
| VRAM locale wan2.7 | **0** — inférence chez Alibaba |
| FITTE vs pile live | oui : n’entre pas dans les 8–10 Go |
| Poids à télécharger | aucun |
| `wan2.7-image` résolutions | 1K / 2K (pas 4K) |
| `wan2.7-image-pro` | 4K en text-to-image seulement |
| `thinking_mode` | défaut true ; plus lent, meilleur ; inactif si image d’entrée ou mode série |
| Prompt | ≤ 5000 caractères |
| `n` | 1–4 ; facturé **par image réussie** |
| URL résultat | 24 h, d’où le download immédiat |
| US Virginia / Frankfurt | wan2.7-image **non listé** sur la page prix du 13 sept (2.6 seulement) |
| Docker `mem_limit` | 8 Go — sans effet ici (pas de poids) |

Ne **pas** charger Wan 2.2 local (TI2V-5B / A14B) « pour faire comme 2.7 » : ce n’est pas le lock, et ça casse le budget VRAM (T5 + DiT, déjà mesuré trop gros pour LingBot).

## Alternative < 2 mois qui FITTE

Le contrat dit : si le modèle est introuvable, une alternative < 2 mois + 2 samples quand même.

Le modèle **n’est pas introuvable** : il est API-only. La barrière est la clé, pas le nom.

Meilleure alternative **récente** qui FITTE pareil (0 VRAM) : **`qwen-image-3.0-pro`** (Model Studio, recommandé à côté de wan2.7-image-pro, sortie ~21 juil. 2026). Même plateforme, **même clé manquante**. Pas un plan B exécutable ce soir.

Local qui tiendrait sur 4070 12 Go, mais **hors fenêtre 2 mois** : `black-forest-labs/FLUX.2-klein-4B` (14 jan. 2026, Apache-2.0, ~8 Go). `Tongyi-MAI/Z-Image-Turbo` (nov. 2025) idem, plus vieux. HunyuanImage-3.0 a des poids : trop gros, pas un fit.

Pas de DL local lancé. Pas de `diffusers` ajouté. Host-agent non touché.

## Non touché

EARS / MOUTH / BRAIN, `src/world`, pas de push, pas de burn. `.env.local` non modifié (pas de clé à y coller).
