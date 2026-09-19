# nights/2026-09-19-WS-RNCP-JEV.md

**Veille ORGA 19 sept** · Hyper Ambient / MOTHER · **pas d'impl** · WS

Sources RNCP: [France Compétences RNCP41889](https://www.francecompetences.fr/recherche/rncp/41889/) · [mescertifs](https://mescertifs.fr/certification/RNCP41889) · Certificateur CALTEA / École Hexagone.

---

## 1) RNCP41889 — BC02 « Déployer des solutions no code / low code fiables et interopérables »

**Intitulé officiel bloc:** *Déploiement de solutions no code/low code fiables et interopérables en réponse aux besoins d'une organisation* (BC02).
**Niveau:** 7 · **Réf. formation citée:** 0022 (interne Hexagone — à croiser syllabus).
**Évaluation type:** mise en situation → **dossier technique** + **soutenance orale avec démonstration**.

### Compétences / livrables attendus (8–12 bullets)

1. **Architecture fonctionnelle** — modéliser entités métiers, traitements, flux de données et interactions plateformes (schémas / cartographie).
2. **Interopérabilité SI** — protocoles d'échange, API, formats, auth ; continuité ERP/CRM/GED/BI et sync données.
3. **UX & accessibilité** — interfaces selon profils/parcours ; standards UX/UI + référentiels accessibilité (PSH).
4. **Flux data** — règles circulation / tri / contrôle / MAJ ; confidentialité + perf ; intégrité des échanges.
5. **Robustesse workflows** — alertes, gestion d'erreurs, scénarios de reprise, notifications, continuité de service.
6. **Services tiers / automatisation / IA** — intégration API/bases/outils d'auto ou IA avec compatibilité, sécurité, éthique et **sobriété** (coût appels, énergie).
7. **Sécurité** — exposition (droits, API, stockage), vulnérabilités tiers, écarts chartes SSI / ISO / RGPD → mesures correctives.
8. **Plan de tests** tech + fonctionnels ; outils de contrôle ; analyse perf / robustesse en conditions réelles.
9. **Qualité & conformité continue** — retours d'usage, contrôles RGPD/RSE/gouvernance data, pérennité.
10. **Évolutions MCO** — priorisation des changes sans rupture ; **documentation** accessible (choix, règles, parcours, flux).
11. **Angle automatisation/interop (utile dossier Hyper Ambient):** chaînes no/low-code (Make/n8n/Zapier-like, Power Platform, Bubble/Soft…) + ponts API/webhooks vers stack locale (agents, TTS, LLM) ; critères d'**interop**, **fiabilité**, **observabilité**, **droits**, **RGPD**.
12. **Annexe 15–30 p. plausible:** architecture cible + diagrammes flux ; matrice outils/critères ; spec API & contrats d'échange ; scénarios test + résultats ; registre risques/RGPD ; runbook déploiement & MCO ; captures démo.

### Angle dossier technique Hyper Ambient / MOTHER
- Positionner MOTHER comme **cœur local** (cerveau + outils) et les briques no/low-code comme **couche d'orchestration / métier** interopérable.
- Montrer **fiabilité** (erreurs, retries, health) et **interop** (HTTP/SSE, files, coffre `nights/`, agents OC/OG) plutôt qu'un MVP "clic seul".

---

## 2) JeV / tout petits modèles déterministes (avant cerveau local)

### JeV (TypeSafe AI) — fait public
- **Quoi:** modèle *System One* (TypeSafe AI, early access ~15 sept 2026) : décisions **structurées typées** + probabilités calibrées, **pas** de génération libre de texte ; sampling **parallèle** ; training RLCD.
- **Usage:** route / classifie / score / branche dans du code ("smart if") — proche d'un "cerveau léger" de décision.
- **Pas GGUF / pas llama.cpp public** à ce jour : **API early access** uniquement.
  Source: https://typesafe.ai/blog/introducing-system-one-models-and-jev
- Pour MOTHER **local**: s'en inspirer (sortie contrainte + temp=0), pas le DL tel quel.

### Top 5 candidats locaux GGUF (llama.cpp) — ultra-légers *avant* un gros cerveau

| # | Modèle | Lien | Taille typ. | Usage possible AVANT cerveau |
|---|---|---|---|---|
| 1 | **SmolLM2-135M-Instruct** | HF GGUF: https://huggingface.co/bartowski/SmolLM2-135M-Instruct-GGUF · base: https://huggingface.co/HuggingFaceTB/SmolLM2-135M-Instruct | Q4_K_M **~110 Mo** | Routeur/intent, tags courts, garde-fous, "oui/non/catégorie" en **temp=0** ; quasi CPU free. |
| 2 | **SmolLM2-360M-Instruct** | https://huggingface.co/bartowski/SmolLM2-360M-Instruct-GGUF | Q4_K_M **~250–280 Mo** | Même rôle + un peu plus de robustesse FR/EN ; pré-filtre avant Occamy/Luciole. |
| 3 | **Qwen3-0.6B** | Officiel: https://huggingface.co/Qwen/Qwen3-0.6B-GGUF · quants bartowski · ModelScope: `Qwen/Qwen3-0.6B` | Q4_K_M **~480 Mo** | Meilleur "mini-cerveau" actuel : tool-ish / JSON / classif plus fiable ; encore léger vs 35B. |
| 4 | **Qwen2.5-0.5B-Instruct** | https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct · GGUF community · MS: `Qwen/Qwen2.5-0.5B-Instruct` | Q4 **~350–400 Mo** | Alternative stable 0.5B ; parsing / reformulation courte / triage tickets. |
| 5 | **TinyLlama-1.1B-Chat** | https://huggingface.co/TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF | Q4_K_M **~670 Mo** | Filet classique llama.cpp ; chat léger / fallback si Smol/Qwen trop faibles. |

**Mode déterministe (tous):** `temp=0` (ou très bas) + seed fixe + schéma de sortie contraint (JSON / enum) — proxy local de l'esprit JeV sans API.

**Hors top / note:** BitNet / LFM très petits = intéressants sobriété mais écosystème GGUF/llama.cpp à vérifier au cas par cas ; JeV reste **distant early-access**, pas un drop-in coffre.

---

*Fin veille — WS 19 sept.*