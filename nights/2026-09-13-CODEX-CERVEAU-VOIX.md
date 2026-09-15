# CODEX CERVEAU — diagnostic voix

Date : 2026-09-13

## Verdict

Le fix n'est pas live au sens fonctionnel : le service actuellement exposé
charge Qwen, mais une vraie transcription finit encore sur :

```text
RuntimeError: Input type (float) and bias type (c10::Half) should be the same
```

Ce n'est plus seulement un problème de vieux PID. Les observations montrent
que le PID actuel a chargé le fichier récent et que le correctif dtype demeure
insuffisant.

## Faits vérifiés en lecture seule

- Conteneur : `mother-core-dev`, actif depuis environ trois heures.
- Source montée : `/workspace/src/ears/qwen3_asr.py`, horodatée
  `2026-09-13 13:38:40 UTC` (`15:38:40` Europe/Paris), 9039 octets.
- Bytecode Python 3.11 : horodaté `13:38:50 UTC`.
- Host-agent : PID `5223`, démarré vers `13:40 UTC` (`15:40` Europe/Paris).
- Le log confirme le chargement Qwen3-ASR en 23,9 s, le warmup EARS, puis
  l'écoute sur `0.0.0.0:8001`.
- À `13:44 UTC`, une vraie requête atteint
  `qwen_asr/.../modeling_qwen3_asr.py:704`, puis `conv2d1` refuse des features
  float32 face à un biais float16.
- Le code fournisseur fait bien :

  ```python
  inputs = inputs.to(self.model.device).to(self.model.dtype)
  ```

  puis appelle `self.model.generate(...)`.
- Le log ne contient pas le message `aligned ... conv layer(s)` du helper
  courant. Ce helper n'a donc pas corrigé le cas réel.
- `dev/scripts/relancer_routeur.sh` se termine actuellement par un simple
  `nohup python ... &`; aucune extinction de l'ancien processus ni validation
  de prise du port n'est effectuée.

## Cause

Il y a deux défauts distincts :

1. Le cycle de vie du service n'est pas déterministe. Modifier un bind mount ne
   recharge pas les imports du processus existant, et le script nommé
   `relancer_routeur.sh` ne remplace pas lui-même cet ancien processus.
2. Le correctif de modèle est incomplet. `dtype=torch.float16` au chargement ne
   garantit pas le dtype effectif des features au point d'entrée du frontend
   audio Qwen quantifié. Dans l'exécution réelle observée, `conv2d1` reçoit
   toujours du float32 alors que son poids/biais est Half.

L'OUT vide de `Cursor -p FIX-VOIX` ne permet pas de conclure qu'il n'a rien
fait : `src/ears/qwen3_asr.py` a changé à 15:38. En revanche, aucune preuve de
transcription réussie n'existe, donc la mission Cursor n'est pas terminée.

## Décision donnée à Cursor

L'ordre détaillé est dans
`nights/2026-09-13-ORDRE-CURSOR-VOIX.md` : cast ciblé des `input_features` à
l'entrée de `wrapper.model.thinker.audio_tower`, tests sans réseau, relance avec
remplacement borné de l'ancien PID, puis recette WebSocket sur
`data/in/question.wav`.

La seule preuve acceptée est une transcription non vide dans la sortie de
`verify_hostagent_loop.py`, avec un unique nouveau PID et aucun nouveau crash
float/Half dans `/tmp/hostagent.log`.

## Actions effectuées par Codex CERVEAU

Inspection uniquement du code, des montages, du PID, des horodatages, de
l'environnement et des logs. Aucun code applicatif modifié, aucun processus
arrêté ou relancé. Seules les deux notes demandées ont été écrites.
