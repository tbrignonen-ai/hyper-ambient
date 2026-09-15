# ORDRE CURSOR — rétablir la voix Qwen3-ASR

Date : 2026-09-13

## But et limite

Cursor est le codeur. Ne pas modifier `world`, le cerveau, la bouche ni le
protocole audio. Corriger uniquement le chemin Qwen3-ASR et rendre la relance
du host-agent déterministe.

Le critère de fin n'est pas « le modèle charge » : il faut obtenir une vraie
ligne `texte transcrit : ...` non vide sans nouvelle occurrence de
`Input type (float) and bias type (c10::Half)`.

## Diagnostic à prendre comme entrée

- `/workspace/src` est un bind mount : le fichier hôte courant est visible
  immédiatement dans le conteneur.
- Python ne recharge pas un module dans un PID déjà vivant.
- Plus important, le PID observé `5223` a démarré après la compilation du
  fichier courant : il a tout de même recrashé dans `conv2d1`.
- `dtype=torch.float16` passé à `from_pretrained` ne garantit donc pas le dtype
  des features que `qwen-asr 0.0.6` remet en forme avant `audio_tower`.
- Le helper actuel `align_unquantized_convs()` n'a imprimé aucune ligne
  `aligned ...` et n'a pas empêché le crash.
- `relancer_routeur.sh` fait seulement un nouveau `nohup`; il ne termine pas
  l'ancien `serve_hostagent.py`. Il peut donc laisser l'ancien PID sur 8001 et
  faire mourir silencieusement le nouveau sur `address already in use`.

## Patch restant — impératif

1. Dans `src/ears/qwen3_asr.py`, après le chargement du wrapper, cibler
   explicitement :

   ```python
   wrapper.model.thinker.audio_tower
   ```

   Installer un `forward_pre_hook` sur cet `audio_tower` qui caste uniquement
   son premier argument flottant, `input_features`, vers :

   ```python
   audio_tower.conv2d1.weight.dtype
   ```

   Préserver sans conversion `feature_lens` et `aftercnn_lens` (tenseurs
   entiers). Conserver une référence du handle sur le wrapper pour rendre le
   cycle de vie explicite. Le hook doit fonctionner avec les arguments
   positionnels de la signature installée :

   ```text
   forward(input_features, feature_lens=None, aftercnn_lens=None)
   ```

   Ne pas modifier les fichiers sous `site-packages/qwen_asr`.

2. Ajouter un test unitaire sans modèle ni réseau qui construit un faux
   `audio_tower` dont `conv2d1` est en `float16`, lui passe des features
   `float32`, et prouve que le corps de `forward` reçoit du `float16`. Ajouter
   aussi les no-op : wrapper incomplet et features non flottantes.

3. Garder `dtype=torch.float16` avec `load_in_4bit=True`. Remplacer ou retirer
   `align_unquantized_convs()` si son objectif devient redondant, mais ne pas
   considérer son compteur comme preuve de correction. Journaliser au
   chargement les deux valeurs utiles : dtype entrant visé et dtype de
   `conv2d1.weight`.

4. Dans `dev/scripts/relancer_routeur.sh`, avant `nohup`, trouver uniquement les
   processus `python ... dev/scripts/serve_hostagent.py`, leur envoyer `TERM`,
   attendre leur disparition avec un délai borné, puis `KILL` seulement ceux
   qui subsistent. Ne jamais employer un `pkill python` large. Après `nohup`,
   attendre que le nouveau PID vive et que `/tmp/hostagent.log` contienne
   `écoute sur 0.0.0.0:8001`; sinon afficher le log et sortir non-zéro.

## Commandes exactes à exécuter après le patch

Depuis `D:\BGB Training\MOTHER-dev` dans PowerShell :

```powershell
docker exec mother-core-dev pytest -q dev/tests/test_qwen3_asr.py
docker exec mother-core-dev bash /workspace/dev/scripts/relancer_routeur.sh
docker exec mother-core-dev bash -lc "pgrep -af 'python(3)? dev/scripts/serve_hostagent.py'; tail -n 80 /tmp/hostagent.log"
docker exec mother-core-dev python dev/scripts/verify_hostagent_loop.py --audio /workspace/data/in/question.wav --out /workspace/data/out/verify_loop_reponse.wav
docker exec mother-core-dev bash -lc "tail -n 160 /tmp/hostagent.log; if grep -q 'Input type (float) and bias type (c10::Half)' /tmp/hostagent.log; then exit 1; fi"
```

## Preuves obligatoires dans OUT Cursor

Copier littéralement :

- le résumé pytest avec zéro échec ;
- l'unique ligne `pgrep` et le nouveau PID ;
- dans le log, les dtypes journalisés et `écoute sur 0.0.0.0:8001` ;
- le rapport de recette avec `texte transcrit` non vide ;
- le verdict de recette ;
- la confirmation qu'aucun crash float/Half n'apparaît depuis la relance.

Si la recette échoue encore, ne pas annoncer « voix réparée ». Capturer les
dtypes réels à l'entrée de `audio_tower` et de `conv2d1.weight`, ainsi que la
trace complète, puis s'arrêter avec un OUT explicite.
