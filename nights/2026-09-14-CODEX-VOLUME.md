# CODEX — volume de la voix

Date : 2026-09-14, demande Thomas 20:42.

## Résultat live

- Voix conservée : **Pocket TTS `estelle`**, langue `french_24l`, CPU.
- Profil conservé : **`aurora`**.
- Gain configuré : **+9,0 dB**, soit **x2,82** autour des faibles niveaux.
- Protection : limiteur doux `tanh`, borné dans `[-1, 1]`, sans écrêtage dur.
- Processus relancé : **host-agent seulement**, PID `11301`.
- Docker et Presence n'ont été ni recréés ni redémarrés.

Le log live confirme :

```text
MOUTH : post-gain sortie +9.0 dB (x2.82), limiteur doux tanh
MOUTH : chargement pocket-tts french_24l / estelle profil=aurora device=cpu demi_tons=+0…
pocket-tts loaded in 81.9s @ 24000 Hz
écoute sur 0.0.0.0:8001 /hostagent
INFO:     Application startup complete.
```

## Où est le gain

Le levier retenu est le **post-gain final de MOUTH côté host-agent**, juste avant
la sérialisation des trames vers le client Windows :

- algorithme : `src/mouth/output_gain.py`, fonction `appliquer_gain_doux` ;
- branchement unique : `dev/scripts/serve_hostagent.py`, méthode `_envoyer` ;
- configuration persistante : `MOUTH_OUTPUT_GAIN_DB=9` dans `.env.local` ;
- valeur de relance : `MOUTH_OUTPUT_GAIN_DB_FORCE`, défaut `9`, dans
  `dev/scripts/relancer_routeur.sh`.

Ce point couvre les deux clients, Presence et Talk, ainsi que la réponse normale,
les amorces et la phrase de secours. Il ne modifie ni le modèle, ni la voix, ni le
profil Aurora. Le volume WASAPI de Windows reste inchangé.

## Avant / après mesuré

Source : `data/out/voix-compare/pocket-estelle.wav`.

Sortie de preuve :
`data/out/voix-compare/pocket-estelle-aurora-plus9db.wav`.

```text
avant rms=-21.11 dBFS peak=-2.76 dBFS
apres rms=-13.55 dBFS peak=-0.23 dBFS delta_rms=+7.56 dB
```

Le gain RMS réel est inférieur aux +9 dB nominaux sur ce sample parce que les
crêtes hautes entrent volontairement dans la zone douce du limiteur. Il reste
nettement dans la cible demandée de +6 à +12 dB.

## Vérifications

```text
51 passed in 1.42s
```

Tests exécutés : gain/limiteur, restitution Talk et gestion des canaux de sortie.

## Retester

1. Écouter le WAV `pocket-estelle-aurora-plus9db.wav` puis le comparer à
   `pocket-estelle.wav` au même volume Windows.
2. Dans Presence, faire un tour vocal normal : toute nouvelle réponse reçue du
   host-agent utilise déjà le gain live.
3. Vérifier le réglage actif :

```powershell
docker exec mother-core-dev sh -lc "grep 'MOUTH : post-gain' /tmp/hostagent.log"
```

Pour essayer une autre valeur sans changer de voix ni de profil :

```powershell
docker exec -e MOUTH_OUTPUT_GAIN_DB_FORCE=6 mother-core-dev bash /workspace/dev/scripts/relancer_routeur.sh
```

Valeurs conseillées : `6` si la compression est trop audible, `9` actuellement,
`12` si la sortie physique reste vraiment faible.
