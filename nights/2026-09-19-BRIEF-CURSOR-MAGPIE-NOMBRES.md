---
date: 2026-09-19
type: brief
cible: Cursor (Grok 4.6)
auteur: Claude (lead technique)
---

# BRIEF Cursor — Magpie : toutes les voix, texte avec nombres

Magpie TTS multilingual 357M est installé : `/workspace/models/tts-bench/magpie` (binaire `bin/nemo-speech`, lancer avec `LD_LIBRARY_PATH=$M/lib`).
Voix intégrées (métadonnées GGUF) : John, Sofia, Aria, Jason, Leo. Thomas a retenu **Aria** ; il veut entendre toutes les voix féminines sur un nouveau texte.

Texte (tester les nombres, point faible relevé en dégustation) :
« Il est quinze heures trente. Ton rendez-vous chez le docteur Lefebvre est jeudi 24 septembre, au 12 rue des Lilas. Veux-tu que je te le rappelle vingt minutes avant ? »

Commande type : `nemo-speech synthesize "<texte>" --voice <Nom> --language fr --device cpu --seed 7 -o <Nom>.wav --force`

## Livrables
- Les 5 voix générées, normalisées RMS −20 dBFS, mono 16 bits, **nommées par voix** (pas d'aveugle cette fois) :
  `nights/degustation-19/voix4-magpie-nombres/magpie2-<Nom>.wav` (écrire dans `/tmp` du conteneur puis `docker cp` avec un chemin Windows).
- Si l'option existe (`--tts.KEY`, `--config`) : une variante **Aria plus lente** (~0,9) ; sinon le dire.
- OUT court : `nights/2026-09-19-MAGPIE-NOMBRES-OUT.md` — genre perçu de chaque voix si détectable (hauteur moyenne F0), temps de synthèse, nombres correctement prononcés ou non (transcrire chaque wav avec faster-whisper déjà installé et comparer).

## Interdits
Ne pas toucher au host-agent, à `:8080`/`:8090`, ni à `src/`, `native/`, `workers/`, `dev/` · pas de `.env.local` · pas de git · CPU seulement (un test cerveau tourne sur le GPU). Réponds seulement OK.
