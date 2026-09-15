# Cursor FIX-VOIX — Qwen3-ASR audio_tower hook

Date : 2026-09-13

## Verdict

Voix rétablie. Critère de fin atteint : `texte transcrit` non vide, zéro
occurrence de `Input type (float) and bias type (c10::Half)` depuis la
relance. World non touché.

Le PID `5223` (celui du diagnostic Codex) a reçu `TERM`. Le nouveau PID
est `6220`.

## Patch

1. `src/ears/qwen3_asr.py` — `install_audio_tower_dtype_hook(wrapper)` pose
   un `forward_pre_hook` sur `wrapper.model.thinker.audio_tower`. Le hook
   caste uniquement `input_features` (1er argument flottant) vers
   `audio_tower.conv2d1.weight.dtype`. `feature_lens` et `aftercnn_lens`
   restent tels quels. Le handle vit sur `wrapper._audio_tower_pre_hook`.
   Wrapper incomplet ou features non flottantes : no-op.
2. `align_unquantized_convs()` retiré : redondant et inefficace (aucune
   ligne `aligned ...` en prod, crash `conv2d1` malgré tout). Conservé
   `dtype=torch.float16` avec `load_in_4bit=True`.
3. `dev/tests/test_qwen3_asr.py` — faux `audio_tower` Half, features
   float32, le corps de `forward` reçoit du float16 ; no-op wrapper
   incomplet ; no-op tenseurs entiers.
4. `dev/scripts/relancer_routeur.sh` — avant `nohup`, `TERM` puis `KILL`
   borné uniquement sur `python … dev/scripts/serve_hostagent.py`. Après
   `nohup`, attente que le PID vive et que le log contienne
   `écoute sur 0.0.0.0:8001`. Pas de `pkill python` large.

Aucun fichier sous `site-packages/qwen_asr`. Aucune modification de
`world`, du cerveau, de la bouche ni du protocole audio.

## Preuves (copiées littéralement)

### pytest — zéro échec

```text
...............                                                          [100%]
15 passed in 0.84s
```

### Relance

```text
cle de 93 caracteres, routeur arme
TERM host-agent: 5223
host-agent relance, pid 6220
host-agent pret, pid 6220
```

### Unique ligne pgrep et nouveau PID

```text
6220 python dev/scripts/serve_hostagent.py
```

### Dtypes journalisés et écoute

```text
audio_tower dtype entrant visé=torch.float16 conv2d1.weight.dtype=torch.float16
audio_tower dtype entrant visé=torch.float16 conv2d1.weight.dtype=torch.float16
…
écoute sur 0.0.0.0:8001 /hostagent
```

(La ligne dtype apparaît deux fois : `print` vers stdout + `logger.info`
capté par le handler transformers. Un seul hook est enregistré.)

### Rapport de recette — texte transcrit non vide

```text
=== Rapport de recette du pont audio ===
  durée audio envoyé     : 4.26 s
  trames envoyées        : 213
  trames reçues          : 550
  mic_to_audible         : 1300 ms  (budget NFR-01 : 1200 ms, > budget)
  durée audio reçu       : 11.00 s
  texte transcrit        : Peux-tu me dire en une phrase pourquoi le facteur temps réel doit rester inférieur à un ?
  réponse du modèle      : Pour qu'une simulation numérique reste stable, la distance parcourue par l'information pendant un pas de temps ne doit pas dépasser la taille d'une maille, ce qui impose un nombre de Courant inférieur à un.
  fichier écrit          : /workspace/data/out/verify_loop_reponse.wav
VERDICT : OK — audio reçu, mais NFR-01 dépassé (1300 ms > 1200 ms)
```

### Log du tour depuis la relance (extrait)

```text
INFO:     127.0.0.1:50276 - "WebSocket /hostagent" [accepted]
INFO:     connection open
Setting `pad_token_id` to `eos_token_id`:151645 for open-end generation.
EARS  : "Peux-tu me dire en une phrase pourquoi le facteur temps réel doit rester inférieur à un ?" — 1032 ms
HTTP Request: POST http://localhost:8080/completion "HTTP/1.1 200 OK"
router: escalate (181 ms)
BRAIN : filler — "Un instant."
HTTP Request: POST https://api.commandcode.ai/provider/v1/chat/completions "HTTP/1.1 200 OK"
MOUTH : premier audio après 3923 ms
BRAIN : "Pour qu'une simulation numérique reste stable, la distance parcourue par l'information pendant un pas de temps ne doit p..."
BRAIN : TTFT 3206 ms
```

### Crash float/Half depuis la relance

```text
NO_FLOAT_HALF_CRASH
```

`grep -q 'Input type (float) and bias type (c10::Half)' /tmp/hostagent.log`
sort avec code 0 côté `else` : aucune occurrence dans le log tronqué par le
`nohup … > /tmp/hostagent.log` de la relance.

## NFR-01

Hors critère de fin de cet ordre. 1300 ms vs budget 1200 ms. La boucle a
quand même produit de l'audio (550 trames, 11 s). Non traité ici.
