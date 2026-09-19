---
date: 2026-09-19
heure: ~19:00
type: note-lead-tech
de: Claude (lead technique)
pour: Codex (exécution) — via Grok bot (organisation, dispatch)
related: ["[[2026-09-19-CLAUDE-POUR-GROK]]", "[[2026-09-19-CLAUDE-POINT-SESSION]]", "[[2026-09-19-NOTE-JEV]]"]
---

# Note lead technique → Codex : phases ultérieures à démarrer

Grok bot organise et distribue ; cette note fixe le **contenu technique** et le **modèle conseillé** par lane.

## Carte des modèles (état 19/09 ~19h)
Cerveau **Granite 4.2 3B Q4_K_M** (llama-server `:8080`, alias `mother-local`) · Voix **Magpie TTS 357M, voix Sofia** (`src/mouth/magpie_tts.py`) ·
Oreille **en cours de choix** (Whisper large-v3 / Parakeet v3 / Canary-1B-v2). Ne rien coder qui dépende du choix de l'oreille.

## Fichiers réservés à Cursor en ce moment — NE PAS TOUCHER
`src/mouth/magpie_tts.py`, `src/mouth/normalize.py`, `native/presence/*`, `native/hostagent/*`, bloc audio/EARS et bloc MOUTH de `dev/scripts/serve_hostagent.py`,
`dev/scripts/banc_oreille.py`, `nights/degustation-19/*`. Pas de relance du host-agent ni de llama-server (Claude fait les tests live avec Thomas).

## Lanes pour Codex (modules neufs, branchement plus tard)

| Lane | Contenu | Modèle conseillé |
|---|---|---|
| **C3 — JeV en entrée** | `src/ears/jev_reflexe.py` : client HTTPS `POST https://api.typesafe.ai/v1/systemone` (`model: jev-latest`, doc : https://docs.typesafe.ai/llms.txt), **connexion gardée ouverte** (mesuré : ~280 ms vs ~690 ms en connexion neuve), **un seul appel** portant les 13 questions ci-dessous, seuils configurables, **repli silencieux** (pas de clé / timeout > 600 ms / erreur → comportement bouton actuel). Clé `TYPESAFE_API_KEY` lue à l'exécution, jamais affichée. Tests avec transport factice ; une preuve live (5 phrases FR du `NOTE-JEV`) avec latences. | **gpt-5.6-terra, reasoning medium** |
| **C4 — Web multi-fournisseurs** | Étendre `src/brain/tools_web.py` : interface fournisseur + **chaîne de repli ordonnée** configurable ; fournisseurs : SearXNG, DuckDuckGo (`ddgs`), Tavily, Brave, Exa, Jina, Serper (+ squelettes Perplexity/Kagi). **D'abord diagnostiquer** pourquoi la recherche web a échoué en live aujourd'hui (voir `2026-09-19-DEGUSTATION-CERVEAUX-RESULTATS.md` §défauts) — cause prouvée avant correctif. | **gpt-5.6-terra, reasoning high** (diagnostic) |
| **C5 — TTS distant** | `src/mouth/remote_tts.py` : backend `MOUTH_BACKEND=remote`, API type `/audio/speech` ; **StepAudio d'abord** (`STEPFUN_BASE_URL` = `https://api.stepfun.ai/step_plan/v1`, modèle `stepaudio-2.5-tts`, voix `elegantgentle-female` vérifiée) ; **catalogue de voix récupéré par API après test de la clé** (jamais codé en dur), repli sur la voix locale. | **gpt-5.6-luna, reasoning medium** |
| **C7 — App native Windows (étude)** | Document `nights/2026-09-19-C7-NATIF-WINDOWS.md` : inventaire de tout ce qui dépend de Docker/Linux (llama-server, EARS, MOUTH Magpie `nemo-speech`, host-agent, chemins, cgroup), équivalent Windows natif pour chacun (llama.cpp CUDA release, faster-whisper/CT2, sherpa-onnx, nemo-speech Windows ?), plan d'installateur (Python embarqué, téléchargement des modèles au 1er lancement, emplacement modèles sur SSD). **Pas de code.** | **gpt-5.6-sol, reasoning high** |
| **C11 — Identité** | Le produit s'appelle **Hyper Ambient** (un cerveau a répondu « ambiance ») : localiser le prompt système du cerveau local et y porter nom + règles (français parlé, pas de markdown, réponses courtes sauf demande). Petit correctif + test. | **gpt-5.6-luna, reasoning low** |

**13 questions JeV (C3)** : adressée à MOTHER · interruption réelle (vs « mmh ») · phrase finie · transcription douteuse · longueur attendue (1 mot / quelques phrases / développée) ·
ton (calme / enjoué / sérieux / empathique) · frustration (échelle) · besoin d'info à jour · référence au contexte · demande de mémorisation · action locale sensible ·
données personnelles · harnais **nommé par l'utilisateur** (aucun / Claude / Codex). Règle produit : **aucun modèle ne décide seul d'envoyer une tâche à un harnais**.

⚠️ Correspondance des niveaux sol / terra / luna = **hypothèse de Claude** (sol = le plus capable, terra = intermédiaire, luna = rapide/léger) : Grok ou Thomas corrige si c'est l'inverse.
Principe : le plus haut niveau pour ce qui exige du jugement (C7, diagnostic C4), l'intermédiaire pour les modules bien spécifiés, le léger pour les petits correctifs.

## Règles communes
TDD (test rouge vu puis vert, sorties collées) · cause racine avant correctif · **fichiers neufs de préférence**, branchement dans `serve_hostagent.py` plus tard par Claude ·
aucune valeur de secret affichée ni écrite · pas de `docker compose up` / recreate · pas de commit (Thomas valide) · OUT par lane : `nights/2026-09-19-<LANE>-OUT.md`.
Ordre suggéré : C11 et C7 d'abord (sans risque), puis C3, C4, C5.

## Ajout ~20h — C4 : cause racine de l'échec web PROUVÉE (Claude, test live)
Test live « météo demain à Marseille » : `web_search` bien déclenché, SearXNG joignable (HTTP 200 sur `http://host.docker.internal:8080`),
mais **0 résultat** : moteurs généralistes suspendus (`duckduckgo: CAPTCHA`, `startpage: CAPTCHA`, `mojeek/yep: access denied`, `wolframalpha: timeout`).
Le code ne bascule sur Tavily que si SearXNG est *injoignable*, pas s'il rend **0 résultat** — et aucune clé Tavily n'est configurée.
→ C4 doit : (1) traiter « 0 résultat » et « moteurs muets » comme un échec qui passe au fournisseur suivant ; (2) chaîne avec au moins un fournisseur par API ;
(3) message vocal clair si tout échoue (« je n'ai rien trouvé sur le web », pas « je ne peux pas consulter le web »).
## Ajout ~20h — outil calculatrice (C12, petit)
Test live : Granite a annoncé 8376 / 2,8 ≈ 2982,857 (juste : 2991,43). Ajouter un outil `calculer` (évaluation arithmétique sûre, sans `eval`) au registre, danger `read`. Modèle conseillé : **gpt-5.6-luna, reasoning medium**.
