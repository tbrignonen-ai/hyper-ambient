---
date: 2026-09-19
heure: ~14:15
type: point-session
auteur: Claude (MOTHER-PLAN-19 — lead technique + interlocuteur tests live)
statut: session en cours
related: ["[[2026-09-19-CLAUDE-POUR-GROK]]", "[[2026-09-19-NOTE-JEV]]", "[[2026-09-19-VEILLE-HF]]", "[[2026-09-19-CLAUDE-PLAN-TECH]]"]
---

# Point session 19 sept — ce qu'il faut retenir

## Étape en cours
**Figer les modèles locaux** (oreille, cerveau, voix) par dégustation à l'aveugle avec Thomas, puis test final.
Le reste (interface, harnais, onboarding…) est orchestré par Grok bot.

## Découverte majeure
Le host-agent tourne **sans la config de Thomas** (log `hostagent-19.log`) : voix Pocket `estelle` (écartée le 8/09),
cerveau MiniCPM5-2B (écarté le 15/09), gain 0 dB, `OUTILS: aucun backend`. Hypothèse : `.env.local` non propagé → lane C1.

## Décisions de Thomas
1. **JeV (TypeSafe) = GO en entrée** (mains libres), pas en sortie. JeV n'écrit pas de texte et ne fait pas de web → ne remplace pas le modèle distant.
2. **Rôles des étages** : JeV = mains libres ; modèle distant = intelligence supérieure + accès outils locaux.
3. **Escalade vers un harnais = toujours décidée par l'utilisateur** (voix ou bouton), jamais par un modèle. Le local répond toujours.
4. **JeV : au moins 10 critères utiles** en un seul appel (12 proposés : adressée, interruption, fin de tour, mal entendu, longueur, ton, frustration, besoin web, référence au contexte, mémoriser, action sensible, données perso + harnais nommé).
5. **Clés API toutes facultatives** : l'appli marche sans clé ; chaque clé ajoute un étage, avec repli.
6. **Recherche web : beaucoup de fournisseurs au choix**, en chaîne de repli (SearXNG, DuckDuckGo, Tavily, Brave, Exa, Jina, Serper, Perplexity, Kagi…).
7. **Option TTS distante obligatoire** (test avec le forfait Step).
8. **Onboarding vocal + visuel** : VRAM et modèles en temps réel, assemblage limité en local / libre en distant ; le modèle local explique, le code vérifie et écrit la config.
9. **Cerveau local bon même avec 10 Go de VRAM au total** (oreille + cerveau + voix).
10. **App native Windows pour l'utilisateur**, Docker = atelier de dev + options avancées (SearXNG, Camunda). « Tourne sous Windows natif » = critère éliminatoire des modèles.
11. **Veille modèles = API Hugging Face**, pas la recherche web des LLM (« plus gros unlocker de la journée »).

## Mesures faites aujourd'hui
- **JeV API** : ~280 ms médiane connexion gardée (dont ~190 ms réseau, ~90 ms modèle), 692 ms connexion neuve ; 1 ou 30 questions = même latence ; bonne discrimination sur 5 phrases FR.
- **NanoJev** (réplique tierce, labyrinthes/jeux, EN/ZH) installé en local : aucune discrimination sur le français → base à ré-entraîner plus tard, pas utilisable.
- **Step-5-preview** (forfait Step Plan) : excellent français, raisonnement juste, mais 3–8 s avant le 1er mot (réflexion non désactivable) → très bon modèle distant, pas un réflexe.
- **StepAudio 2.5 TTS** : fonctionne (voix `elegantgentle-female`, ~3,8 s par phrase) ; catalogue de voix non accessible avec la clé du forfait ; clonage de voix possible.
- Recherche web : Tavily 1 000 crédits/mois sans carte ; Brave 5 $/mois avec carte (vérifié 19/09).

## Dégustation en cours
- **Voix** : 4 échantillons à l'aveugle, même phrase, même volume → `nights/degustation-19/degustation-voix-A..D.wav` (2 Supertonic F5/F3 à 0,88, 2 StepAudio). **Classement de Thomas attendu.**
- **Veille HF** (Cursor) : `nights/2026-09-19-VEILLE-HF.md` + `dev/scripts/veille_hf.py` (38 tests verts). Section cerveau refaite sans biais « tag fr » ; oreille et voix en cours de refonte avec les généralistes.
- Reste à déguster : oreille (Whisper turbo, Qwen3-ASR, Parakeet v3, Kyutai 1B, Nemotron-3.5-ASR, Canary-1B-v2…), cerveau (Luciole-8B vs nouveaux 4–9B), voix (+ nouveautés veille).

## Clés et accès (valeurs jamais affichées, toutes dans `.env.local`)
`TYPESAFE_API_KEY` (OK) · `STEPFUN_API_KEY` + `STEPFUN_BASE_URL=https://api.stepfun.ai/step_plan/v1` (OK : step-5-preview, step-3.7-flash, stepaudio-2.5-tts/asr) ·
`HF_TOKEN` (**refusé 401** — à régénérer en « Read » avant de télécharger des modèles à accès restreint) · `BRAIN_API_KEY` = routeur commandcode.ai (71 modèles, pas Step-5).
⚠️ Les clés JeV, Step et HF ont transité en clair dans le chat → à régénérer après la session.

## Installé aujourd'hui (conteneur, hors git)
`models/nanojev`, `models/nanojev-src`, `models/nanojev-deps` (tqdm isolé ; venv FireRed intact).

## Décisions ajoutées (~14:45)
12. **Voix distantes = intégration**, hors dégustation : l'appli permettra de brancher n'importe quel TTS distant. Dans l'onboarding, après test de la clé, le modèle propose le choix parmi les voix disponibles chez ce fournisseur.
13. **Cette étape vient vers la fin de l'onboarding** (elle demande l'accès web et, de préférence, le modèle texte distant).
14. **Règle de répartition** : question simple d'onboarding → modèle local ; question complexe → **modèle distant en priorité, local en repli**.
15. Voix locale : F5 0,88 gagnante à l'aveugle contre F3 et 2 voix Step, **mais pas figée** — banc n°2 des nouveautés HF en cours.
16. **Une fois la carte figée, seuls les modèles locaux retenus pour le package sont copiés sur le SSD `E:`** (pas le reste de la cave).
17. **Voix — banc n°2 à l aveugle : Thomas préfère J = nvidia/magpie_tts_multilingual_357m, voix Aria** (CPU, 0 VRAM, Windows natif, 7,4 s pour 10 s d audio), devant Supertonic F5, Audio8 (132 s, trop lent) et OmniVoice (74 s, licence NC). Favorite ; licence NVIDIA Open Model à vérifier ; débit à ralentir.
18. **VOIX LOCALE RETENUE : Magpie TTS multilingual 357M (NVIDIA), voix Aria (speaker 2)** — choisie deux fois à l aveugle (J au banc 2, N au banc Magpie) : « super claire et compréhensible ». CPU, 0 VRAM, ~temps réel, Windows natif, usage commercial autorisé. Débit à ralentir si possible (pas de réglage natif documenté).
19. **Version EN livrée en 0.1 en même temps que la FR** (portée GitHub). FR reste la langue de base et de la soutenance (100 % FR). Conséquence : préférer un cerveau multilingue (Luciole = FR seul) ; Magpie Aria parle aussi anglais.
20. **CERVEAU LOCAL RETENU : Ministral-3-8B-Instruct-2512 Q4_K_M** — 5,0/5 à l aveugle (NeoHorse-9B 4,0 ; Luciole 2,7 pénalisé par appli tombée ; NeoHorse-4B 2,0). Multilingue (FR + EN), outils natifs. Détails + défauts relevés : [[2026-09-19-DEGUSTATION-CERVEAUX-RESULTATS]].
21. **Voix Magpie : SOFIA retenue** (« de loin la mieux » sur le texte avec nombres) — remplace Aria. Magpie ne lit pas les nombres en chiffres → normalisation nombres→lettres nécessaire avant la synthèse ; pas de réglage de débit natif.
22. Ministral-3-8B = **repli seulement** (jugé trop vieux) ; Granite 4.2 3B en test oral ; NeoHorse-9B 2e choix.
23. **CERVEAU LOCAL RETENU : IBM Granite 4.2 3B (Q4_K_M, 2,2 Go)** — 4,57/5 à l oral (7/7 thèmes), multilingue FR+EN, Apache 2.0, outils ; plus léger que Ministral (5,0 mais jugé trop vieux, repli) → libère de la VRAM pour la voix.
24. Oreille : WS recommande Parakeet v3 (11 %) par défaut, Whisper turbo + hotwords en repli, **Voxtral-Mini-4B-Realtime à déguster** avant de figer. Whisper large-v3 : mesure Cursor interrompue (fin de session précédente).
23. **CERVEAU LOCAL RETENU : Granite 4.2 3B Q4_K_M** (4,57/5 à l oral, ~3 Go VRAM, Apache-2.0, FR+EN) ; replis NeoHorse-9B puis Ministral.
24. **CARTE FIGÉE** (~20h15) : Granite 4.2 3B Q4_K_M · Whisper large-v3 int8 · Magpie Sofia CUDA → [[2026-09-19-CARTE-FIGEE]] ; suite orga → [[2026-09-19-CLAUDE-POUR-GROK-SUITE]].
