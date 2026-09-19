---
date: 2026-09-19
type: out
cible: magpie-nombres
---

# MAGPIE NOMBRES — OUT

Texte : « Il est quinze heures trente. Ton rendez-vous chez le docteur Lefebvre est jeudi 24 septembre, au 12 rue des Lilas. Veux-tu que je te le rappelle vingt minutes avant ? »

Conteneur `mother-core-dev` · `nemo-speech synthesize` · `--language fr --device cpu --seed 7` · WAV mono PCM16 22050 Hz · RMS −20 dBFS · GPU non utilisé.

## Aria plus lente (~0,9)

**Option inexistante.** `--tts.speed 0.9` → `unknown option: --tts.speed`. Les clés `--tts.KEY` / `--config` couvrent seed, steps, temperature, cfg-scale, backends ; pas de débit / length-scale / rate.

## Voix

| Voix | Genre perçu (F0 moy.) | Synthèse | Durée audio | Nombres | Transcription faster-whisper (large-v3-turbo, CPU) |
|---|---|---:|---:|---|---|
| John | ambigu (174 Hz) | 9.473 s | 11.378 s | 15h30 et 20 min OK ; **24 et 12 absents** | il est quinze heures trente ton rendez-vous chez le docteur lefèvre est jeudi septembre aux eaux rues des lilacs veux-tu que je te le rappelle vingt minutes avant |
| Sofia | féminin (197 Hz) | 8.275 s | 9.845 s | 15h30 et 20 min OK ; **24 et 12 absents** | Il est 15h30. Ton rendez-vous chez le Dr Lefebvre est jeudi septembre au Hérud et Lilas. Veux-tu que je te le rappelle 20 minutes avant? |
| Aria | féminin (212 Hz) | 8.021 s | 9.706 s | 15h30 et 20 min OK ; **24 et 12 absents** | Il est 15h30. Ton rendez-vous chez le docteur Lefèvre est jeudi, ce septembre, au Eau rue des Lilas. Veux-tu que je te le rappelle 20 minutes avant ? |
| Jason | masculin (142 Hz) | 8.243 s | 9.660 s | 15h30 et 20 min OK ; **24 et 12 absents** | Il est 15h30. Ton rendez-vous chez le docteur Lefebvre est jeudi ce septembre, aux rues des Lilas. Veux-tu que je te le rappelle 20 minutes avant ? |
| Leo | féminin (210 Hz) | 9.094 s | 10.588 s | 15h30 et 20 min OK ; **24 et 12 absents** | Il est 15h30. Ton rendez-vous chez le docteur Lefebvre est jeudi au septembre au IE rue des Lilas. Veux-tu que je te le rappelle 20 minutes avant ? |

Féminines par F0 : **Sofia, Aria, Leo**. Jason masculin. John dans la zone de recouvrement.

## Nombres

Les formes **en lettres** (« quinze heures trente », « vingt minutes ») passent (ASR : 15h30 / vingt ou 20 minutes). Les **chiffres arabes** `24` et `12` ne sont reconnus sur aucune voix (trou à la place de 24 ; 12 lu comme eaux / Hérud / Eau / rues / IE). Point faible confirmé.

WAV : `nights/degustation-19/voix4-magpie-nombres/magpie2-<Nom>.wav`.
