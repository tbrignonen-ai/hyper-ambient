---
date: 2026-09-13
type: assign
to: Cursor
---
# ASSIGN — 10 samples MP3 voix FR (message long)

Thomas 17:38 : sampler **10 voix FR differentes** avec des modeles TTS compatibles differents ; message **long** ; objectif esthetique **Aura Ray** (YouTube) — douce, presentielle, proche. Il ecoute apres. Ping OC via OUT quand les 10 MP3 sont prets.

Autorise : telecharger d autres modeles TTS FR si besoin ; supprimer dans le perimetre models/ ceux que vous n utiliserez plus (Piper rejects OK a nettoyer si place, mais garder au moins un fallback Piper siwis jusqu a decision Thomas).

## Script (obligatoire, meme texte pour les 10)
Fichier : nights/2026-09-13-SCRIPT-VOIX-LONG.txt

## Livrable
Dossier : `D:\BGB Training\MOTHER-dev\data\out\voix-10-samples\`
Fichiers : `01-....mp3` … `10-....mp3` (mp3 pas wav) + `INDEX.md` (modele, voix, profil, chemin)
OUT coffre : `nights/2026-09-13-CURSOR-VOIX-10-SAMPLES.md`

## Mix suggere (adapter selon ce qui marche vraiment)
1 pocket estelle
2 pocket autre embedding FR si dispo
3 piper siwis+aurora
4 piper upmc+aurora (jessica)
5 piper mls+aurora
6 piper tom+aurora (avec resample 22k)
7-10 : telecharger / activer d autres TTS FR legers (supertonic styles, autres pocket, qwen3-tts si deja sur disque et raisonnable CPU/VRAM) — viser des timbres differents, preferer feminin doux style Aura Ray

Contraintes : budget VRAM produit ~8-10 Go pour la stack live ; les samples peuvent etre CPU. Ne casse pas le hostagent live (Pocket estelle) sauf si necessaire pour generer — dans ce cas restaure Pocket estelle a la fin.

Preuve : 10 fichiers mp3 existent, duree chacune > 20s idealy, INDEX.md rempli.
