---
date: 2026-09-19
type: brief
cible: Cursor (Grok 4.6)
auteur: Claude (lead technique)
lane: C10 — bug « premier tour sans réponse »
---

# BRIEF Cursor — C10 : la première question reste souvent sans réponse

**Symptôme (Thomas, test live)** : à la première interaction d'une session, MOTHER ne répond pas ; il faut répéter. Ensuite tout marche.
**Constat du 19/09 18h50** (`/workspace/logs/hostagent-degustation.log`) : dans la session observée le 1er tour a fonctionné, donc bug intermittent.
L'appli fait de nombreux `GET /` (404) avant d'ouvrir `WebSocket /hostagent`, ouvert juste avant le 1er EARS.

## Hypothèses à départager (ne rien corriger avant preuve)
1. **Connexion WebSocket ouverte tardivement** : un push-to-talk avant l'ouverture → audio perdu sans message.
2. **Flux micro à démarrage paresseux** (correctif « souffle au démarrage » du 8/09) : la 1re prise perd son début ou tout son contenu.
3. Premier segment audio trop court / VAD ou EARS qui rend une transcription vide au 1er tour (warmup).
4. Autre cause trouvée dans le code.

## Méthode
Lire `native/presence/*`, `native/hostagent/*` (côté Windows) et le chemin audio → EARS de `dev/scripts/serve_hostagent.py`.
Ajouter une **trace minimale** (horodatage : appui PTT, ouverture WS, 1er chunk audio envoyé/reçu, taille audio, transcription) ;
reproduire en relançant l'appli Presence puis un tour (script de test côté client si possible, sinon laisser les traces pour le prochain test de Thomas).
Écrire la cause prouvée, puis test rouge qui la reproduit, puis correctif minimal, puis vert.

## Périmètre
`native/presence/*`, `native/hostagent/*`, partie réception audio/EARS de `serve_hostagent.py` (pas le bloc MOUTH : un autre run Cursor modifie `src/mouth/magpie_tts.py`), tests associés.
Ne pas relancer llama-server. Relancer le host-agent seulement via `/tmp/relance_hostagent.sh` et **pas avant** que la section « GPU » existe dans `nights/2026-09-19-C9-MAGPIE-OUT.md`. Pas de git, pas de `.env.local`.
OUT : `nights/2026-09-19-C10-PREMIER-TOUR-OUT.md`. Réponds OK.
