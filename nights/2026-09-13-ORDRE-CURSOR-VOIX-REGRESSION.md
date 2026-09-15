---
date: 2026-09-13
type: ordre-cursor
incident: voix-regression-17h05
priorite: P0
---
# ORDRE CURSOR — régression voix 17:05

## But et limite

Rendre la parole continue et revenir au couple validé le 8 septembre : Piper
`fr_FR-siwis-medium` + profil `aurora`. Ne pas changer EARS, World, la présence
visuelle ni les modèles pendant cette réparation. Codex a fait le diagnostic ;
Cursor code et vérifie.

## Diagnostic à tenir pour acquis

1. Le runtime a bien été reverté : PID unique `7100`, Piper `siwis`, profil
   `aurora`, 22 050 Hz. Ce revert n'est pas persistant : `.env.local`,
   `.env.example`, `relancer_routeur.sh`, `serve_hostagent.py` et
   `piper_tts.py` portent encore `upmc` ou `mother` comme défaut.
2. Le changement causal le plus proche du feedback est bien
   `siwis+aurora -> upmc+mother`. `mother` ajoute 22 % de réverbe, un doublage
   retardé de 17 ms et ralentit Piper de 16 %. Il peut donner une impression de
   voix brouillée/découpée. `aurora` n'a aucun doublage et seulement 5 % de
   réverbe.
3. `tom-mother.wav` à 44,1 kHz n'est pas joué en production. `upmc` et `siwis`
   sont tous deux à 22,05 kHz. Le serveur les convertit explicitement en 16 kHz.
   Donc le WAV `tom` n'explique pas la régression.
4. La sortie Windows active est néanmoins Sound Blaster Z / MME, native
   44,1 kHz, alors que `OutputStream` est ouvert à 16 kHz. Il existe donc un SRC
   implicite 16 -> 44,1 kHz dans PortAudio/pilote. Ce n'est pas propre au switch
   `upmc`, mais c'est un risque réel d'underrun.
5. Un seul client `pythonw native/presence/app.py` et un seul host-agent sont
   actifs : le double speak n'est pas observé.
6. La recette actuelle concatène les trames reçues sans conserver leurs temps
   d'arrivée. Elle ne peut donc pas voir un trou WebSocket ou un underrun. Un WAV
   « continu » ne prouve pas une lecture continue.
7. Le serveur envoie au plus une seconde par message. Le client fait un
   `recv()`, puis un `OutputStream.write()` bloquant. Il n'existe ni mesure des
   gaps, ni compteur d'underflow, ni tampon de lecture explicite.

## P0 — figer immédiatement siwis + aurora

Faire ces remplacements exacts, sans toucher aux corpus de labo :

```diff
--- .env.local
-MOUTH_VOICE=/workspace/models/piper/fr_FR-upmc-medium.onnx
-MOUTH_PROFILE=mother
+MOUTH_VOICE=/workspace/models/piper/fr_FR-siwis-medium.onnx
+MOUTH_PROFILE=aurora

--- .env.example
-MOUTH_VOICE=/workspace/models/piper/fr_FR-upmc-medium.onnx
-MOUTH_PROFILE=mother
+MOUTH_VOICE=/workspace/models/piper/fr_FR-siwis-medium.onnx
+MOUTH_PROFILE=aurora

--- dev/scripts/relancer_routeur.sh
-export MOUTH_VOICE="${MOUTH_VOICE_FORCE:-/workspace/models/piper/fr_FR-upmc-medium.onnx}"
-export MOUTH_PROFILE="${MOUTH_PROFILE_FORCE:-mother}"
+export MOUTH_VOICE="${MOUTH_VOICE_FORCE:-/workspace/models/piper/fr_FR-siwis-medium.onnx}"
+export MOUTH_PROFILE="${MOUTH_PROFILE_FORCE:-aurora}"

--- dev/scripts/serve_hostagent.py
-VOIX_PIPER = "/workspace/models/piper/fr_FR-upmc-medium.onnx"
+VOIX_PIPER = "/workspace/models/piper/fr_FR-siwis-medium.onnx"

--- src/mouth/piper_tts.py
-DEFAULT_VOICE = "/workspace/models/piper/fr_FR-upmc-medium.onnx"
+DEFAULT_VOICE = "/workspace/models/piper/fr_FR-siwis-medium.onnx"
```

Dans `serve_hostagent.py`, remplacer aussi les deux replis de profil
`os.getenv("MOUTH_PROFILE", "mother")` par `aurora`. Dans les scripts de prod
touchés aujourd'hui (`pipeline_demo.py`, `smoke_test.py`,
`swap_option2_models.py`), remettre les mêmes défauts. Ne pas modifier
`_voix_compare.py`, `banc_*` ni les WAV de comparaison.

Relancer sans variables `FORCE`, puis prouver que le défaut persiste :

```powershell
docker exec mother-core-dev bash /workspace/dev/scripts/relancer_routeur.sh
docker exec mother-core-dev sh -lc "pgrep -af 'python .*dev/scripts/serve_hostagent.py'; grep -E 'MOUTH : chargement|PiperTTS:|voice loaded|écoute sur' /tmp/hostagent.log"
```

Attendu : une seule ligne PID, `fr_FR-siwis-medium.onnx`, `profile=aurora`,
`22050 Hz`.

## P1 — mesurer le trou réel avant de changer le protocole

Ajouter un diagnostic temporaire derrière `AUDIO_DIAG=1` :

- serveur, dans `HostPipeline._envoyer` : numéro de paquet, nombre de trames,
  durée audio (`len(trames) * 20 ms`) et intervalle monotone depuis l'envoi
  précédent ;
- client, dans `consommer_reponse` : intervalle monotone entre paquets, durée
  audio reçue et valeur booléenne rendue par `OutputStream.write()`
  (`underflowed`) ;
- faire retourner cette valeur par `moteur._jouer` au lieu de la jeter ;
- journaliser le périphérique, l'API hôte, le taux demandé (16 kHz), le taux
  natif (44,1 kHz ici), `latency`, `blocksize` et `write_available`.

Ne pas mettre ces logs à chaque tour en production. Les tests doivent couvrir
le mode diagnostic et son absence par défaut.

Recette manuelle : trois réponses d'au moins 12 secondes, dont une avec
plusieurs phrases. Pour chaque paquet `n`, vérifier :

```text
gap_arrivee_ms <= audio_du_paquet_precedent_ms - marge_buffer_ms
underflowed == false
```

Interprétation :

- gap serveur déjà trop grand : starvation BRAIN/TTS entre deux énoncés ;
- serveur régulier, gap client grand : WebSocket/thread Windows ;
- paquets réguliers, `underflowed=true` : PortAudio/MME ou format de sortie ;
- aucun trou temporel : perception causée par voix/profil/segmentation, garder
  le revert et ne pas réécrire le transport.

## P1 — correctif audio selon la preuve

Si underrun/gap client est confirmé, remplacer la lecture directe
`recv -> write` par un producteur/consommateur borné dans
`native/presence/app.py` et le moteur partagé :

- le thread WebSocket ne joue plus le son ; il empile les `float32` mono 16 kHz ;
- un unique worker audio possède `OutputStream` et écrit dans l'ordre ;
- prélecture initiale bornée à 120 ms (6 trames), sans attendre une seconde ;
- capacité 3 secondes ; aucune perte silencieuse ; overflow et underflow sont
  comptés et affichés ;
- le marqueur de fin attend que la file soit vidée avant `_reposer` ;
- pas de deuxième `OutputStream`, pas de deuxième client WebSocket ;
- conserver l'ordre audio -> rapport -> marqueur vide.

Si MME reste en underflow, ouvrir au taux natif du périphérique et faire un
seul rééchantillonnage continu 16 kHz -> taux natif par tour. Ne jamais appeler
un resampler stateless paquet par paquet. Ajouter `--api` à `presence/app.py`
et le transmettre à `choisir_sortie`; tester MME puis WASAPI, sans pinner un
indice numérique instable.

Si le serveur affame réellement la lecture entre deux synthèses, supprimer
l'ouverture agressive arbitraire à 34 caractères pour Piper ou la réserver au
seul filler. Une réponse normale doit être synthétisée par phrase complète ;
ne pas découper au milieu d'une proposition. Mesurer TTFA et continuité avant
de retenir ce changement.

## P1 — tests obligatoires

Ajouter des tests déterministes, sans matériel :

1. paquets avec gigue 0/40/80 ms : zéro underflow après prélecture ;
2. ordre exact des échantillons et durée conservée ;
3. fin de tour : file vidée avant `stop`, dernier mot non tronqué ;
4. deux tours : aucun état audio partagé ;
5. overflow/underflow incrémentent un compteur et ne passent pas en silence ;
6. 22 050 -> 16 000 et, si SRC hôte ajouté, 16 000 -> 44 100 continus aux
   coutures ;
7. présence de messages `state` et `report` entre paquets sans rupture audio.

Commandes :

```powershell
pytest -q dev/tests/test_resample_continu.py dev/tests/test_talk_channels.py dev/tests/test_talk_diagnostic.py dev/tests/test_talk_diagnostic_wasapi.py dev/tests/test_hostagent_transport.py
docker exec mother-core-dev python dev/scripts/verify_hostagent_loop.py --audio /workspace/data/in/question.wav --out /workspace/data/out/verify_loop_reponse.wav
docker exec mother-core-dev sh -lc "tail -n 250 /tmp/hostagent.log"
```

La recette automatique n'est pas le critère final : Thomas doit entendre trois
tours via `native/presence/app.py`, sans trou ni effet de doublage.

## P2 — qualité des réponses

Constat prouvé : la question sur le facteur temps réel a été classée
`escalate`, puis MiniMax-M3 a donné une réponse hors sujet sur le nombre de
Courant. MiniCPM5-2B n'a donc pas produit cette mauvaise réponse ; il sert au
classement et aux seuls réflexes. Le prompt système règle surtout la persona et
la forme vocale, pas la rigueur. La température implicite est `0.7`. Enfin le
runtime dit `OUTILS: aucun` : aucune analyse Codex n'est accessible à la voix.

Patch minimal :

1. Passer la température de génération des réponses à `0.2` (le classifieur
   reste à `0`).
2. Ajouter au prompt système, avant les exemples :

```text
Comprends exactement la question avant de répondre. Pour une question factuelle,
de calcul ou d'analyse, raisonne silencieusement et vérifie que chaque phrase
répond au sujet demandé. N'invente pas. Si une donnée manque ou si le terme est
ambigu, dis-le brièvement et pose une seule question de clarification.
```

3. Garder la politique : seulement salutations/politesse/ordres immédiats en
   local ; connaissance, calcul, comparaison et analyse doivent escalader.
4. Ne pas ajouter davantage de fillers. Une amorce maximum avant la réponse ;
   les lignes `HOLDING` ne doivent apparaître que si le silence dépasse
   réellement 6 secondes.
5. Ne pas prétendre que Codex analyse tant que `CODEX_BRIDGE_TOKEN` est absent.
   Le pont est une amélioration séparée, pas un prérequis du retour voix.

Avant tout changement de modèle distant, lancer un mini-gate fixe de 10 cas :
heure de fin, définition du facteur temps réel, causalité simple, comparaison,
ambiguïté, deux suivis anaphoriques et trois réflexes. Exiger 10/10 de routage
et 0 réponse factuellement fausse. Conserver transcript, route, modèle,
réponse, TTFT et verdict dans le compte rendu Cursor.

## Critères de fin

- siwis + aurora persistent après relance sans `FORCE` ;
- un seul host-agent et un seul client audio ;
- trois écoutes longues sans coupure selon Thomas ;
- aucun underflow observé sur la recette instrumentée ;
- aucune régression des tests ciblés ;
- réponse exacte et centrée sur les 10 cas du gate ;
- rapport Cursor avec mesures avant/après, pas seulement « WAV produit ».
