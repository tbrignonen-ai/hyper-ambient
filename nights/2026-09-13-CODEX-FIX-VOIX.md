# Correctif voix — Qwen3-ASR Q4

Date : 2026-09-13

## Résultat

Le crash `RuntimeError` float/Half du premier `conv2d` est corrigé dans
`src/ears/qwen3_asr.py` pour le chargement CUDA en 4 bits.

Le chargement passe désormais explicitement `dtype=torch.float16` avec
`load_in_4bit=True`. Bitsandbytes quantifie les couches linéaires, mais pas le
frontend audio `conv2d1..3`. Qwen-ASR convertit ses features vers
`model.dtype` avant l'inférence : sans dtype explicite, elles pouvaient rester
en float32 alors que les poids et biais convolutionnels étaient en float16.

Le chemin CPU reste inchangé : ni 4-bit, ni float16 forcé.

## Tests ajoutés

`dev/tests/test_qwen3_asr.py` vérifie maintenant que :

- CUDA + Q4 transmet simultanément `load_in_4bit=True` et
  `dtype=torch.float16` ;
- le backend CPU ne reçoit aucun de ces deux paramètres.

## Validation dans cette session

- inspection du chemin officiel Qwen-ASR : les entrées processeur sont
  converties vers `self.model.dtype`, puis arrivent dans `conv2d1` ;
- contrôle visuel du patch effectué ;
- aucun changement dans `world` ou Hermes ; aucun push ;
- tests Python non exécutés : aucun interpréteur Python local accessible ;
- tests et smoke GPU non exécutés : accès Docker refusé sur
  `npipe:////./pipe/docker_engine` par le profil système de la session.

### Reprise Codex — contrôle de bout en bout

Le 13 septembre, une seconde tentative a vérifié le service exposé depuis
l'hôte :

- `127.0.0.1:8001` accepte bien les connexions TCP ;
- la poignée de main WebSocket `/hostagent` répond `{"type":"ready"}` ;
- un vrai `question.wav`, rééchantillonné de 22 050 Hz vers 16 kHz, a envoyé
  213 trames de 320 échantillons en `float32` ;
- le processus présent a répondu `state=ecoute`, puis une fin de tour vide en
  298 ms, sans message `report` et donc sans transcription observable.

Ce comportement prouve que l'instance actuellement exposée n'a pas été
remplacée par le code courant : avec le transport courant, `on_frames` rend la
coroutine et `create_transport_app` l'attend. La réponse vide immédiate est la
signature de l'ancienne instance détachée, pas une validation du correctif
float/Half. Aucun crash float/Half n'a donc été observé, mais le chemin réel
Qwen corrigé n'a pas non plus été exercé.

## Relance host-agent

Tentative effectuée avec :

```bash
docker exec mother-core-dev bash /workspace/dev/scripts/relancer_routeur.sh
```

Résultat : refus d'accès au moteur Docker avant exécution du script. Le service
actuel répond toujours sur le port 8001, mais il n'a pas rechargé le correctif.

Relance restant à faire depuis une session autorisée :

```bash
docker exec mother-core-dev bash /workspace/dev/scripts/relancer_routeur.sh
docker exec mother-core-dev pytest -q dev/tests/test_qwen3_asr.py
docker exec mother-core-dev tail -n 120 /tmp/hostagent.log
```

## Repli Whisper Turbo

Non activé. Le correctif Qwen est ciblé et cohérent avec le frontend Half ;
basculer `relancer_routeur.sh` sans pouvoir relancer ni vérifier aurait laissé
la voix dans le même état tout en masquant le correctif.

Si Qwen échoue encore après relance, repli temporaire pour aujourd'hui :

```bash
export EARS_BACKEND=faster-whisper
export EARS_MODEL=large-v3-turbo
export EARS_DEVICE=cuda
export EARS_COMPUTE_TYPE=int8_float16
```

Ces quatre valeurs doivent remplacer temporairement les exports EARS dans
`relancer_routeur.sh`, qui les fixe actuellement en interne, puis le script doit
être relancé. Elles ne peuvent pas être simplement préfixées à la commande.
