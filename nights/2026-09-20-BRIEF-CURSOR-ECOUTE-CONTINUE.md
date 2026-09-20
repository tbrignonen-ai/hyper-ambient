# BRIEF Cursor — ECOUTE CONTINUE (le vrai mains libres)
Date : 2026-09-20 ~18h30. Lead technique : Claude (Opus). Design ci-dessous = a suivre.
Tes deux lanes precedentes (JEV-CONNEXION-UI, JEV-PRECHAUFFAGE) sont validees. Merci.

## Le constat qui motive cette lane
Le mode « mains libres » actuel N'EST PAS mains libres. La boucle de capture de
`native/presence/app.py` est conditionnee a l'evenement `tenu` : le micro ne s'ouvre
que si l'utilisateur appuie sur le bouton Parler. Le mode ne fait que remplacer
« maintenir » par « un appui pour demarrer, un appui pour envoyer ».

Thomas, mot pour mot : « OUI C'EST BIEN CA, SINON C'EST PAS DU MAINS LIBRE » — il veut
ne RIEN toucher : micro ouvert en continu, tours delimites par le silence, et JeV qui
filtre ce qui ne lui est pas adresse. JeV existe precisement pour ca : sa question
`addressed_to_mother` n'a de sens que si le micro capte aussi ce qui ne lui est pas destine.

## Perimetre STRICT — n'ecris QUE dans ces fichiers
- `native/hostagent/windows_audio.py`
- `native/presence/app.py`
- `dev/tests/test_ecoute_continue.py` (a creer)

INTERDIT : `src/ears/*`, `src/mouth/*`, `src/i18n/*`, `dev/scripts/*`, `.env.local`.
INTERDIT : lancer Presence, commiter, creer une branche, toucher a git.
(Ta premiere lane a laisse un `.git/index.lock` orphelin — n'execute AUCUNE commande git.)

## DESIGN IMPOSE — ne pas improviser autre chose

### 1. `windows_audio.py` : capture continue segmentee
`PushToTalkCapture` accumule dans `self._trames` et ne rend qu'au `stop()`. Ajoute une
classe `CaptureContinue` (ou etends proprement l'existante SANS changer son comportement
actuel : le PTT marche, il ne doit rien perdre).

Elle doit :
- garder le flux OUVERT en permanence entre `start()` et `stop()` ;
- calculer le RMS de chaque bloc recu dans le callback ;
- calibrer le bruit ambiant sur les ~500 premieres ms, puis retenir un seuil
  `seuil = max(PLANCHER_RMS, bruit_ambiant * FACTEUR)` — expose ces deux constantes,
  nommees et commentees ;
- considerer qu'un tour COMMENCE apres >= 150 ms au-dessus du seuil (evite les clics) ;
- considerer qu'un tour SE TERMINE apres >= `TURN_SILENCE_MS` sous le seuil.
  Lis cette valeur de l'environnement (`TURN_SILENCE_MS`, defaut 700) — elle est deja
  dans la configuration du projet ;
- exposer `segment_pret() -> bool` et `prendre_segment() -> list[AudioFrame]` qui rend
  les trames du tour ecoule ET les retire du tampon, SANS fermer le flux ;
- jeter un segment de moins de 400 ms (toux, bruit) sans le rendre ;
- couper d'office un segment a 15 s (securite anti-blocage) ;
- exposer `suspendre()` / `reprendre()` qui cessent/reprennent l'accumulation sans
  fermer le flux.

Le callback audio est sur un thread temps reel : pas de `print` par bloc, pas de verrou
long. Utilise une structure simple et protege le tampon partage.

### 2. `app.py` : brancher la boucle
Dans `_boucle_tours` (vers la ligne 586), quand `self.mains_libres` est vrai :
- NE PAS attendre `tenu`. Demarrer la capture continue des que le canal est pret.
- Boucler : des que `segment_pret()`, prendre le segment et l'envoyer exactement comme
  aujourd'hui (meme message `audio.capture`, meme champ `mains_libres`).
- Le bouton Parler doit CONTINUER de fonctionner en mains libres (appui = envoyer tout de
  suite le segment en cours, sans attendre le silence). On n'enleve rien a l'utilisateur.
- Quand `mains_libres` repasse a faux, revenir exactement au comportement PTT actuel.

### 3. PIEGE CRITIQUE — l'echo. Ne pas l'oublier.
En ecoute continue, le micro capte la voix de l'assistante et elle se repondrait a
elle-meme en boucle. La session a deja un evenement `self.en_lecture` (mis pendant la
restitution audio). **Tant que `en_lecture` est set, la capture doit etre suspendue**, et
reprise APRES la fin de lecture avec une garde de ~250 ms pour laisser mourir la reverberation.
C'est non negociable : sans ca la fonction est inutilisable.

### 4. Ce qui ne change pas
- Le filtrage « est-ce que ca m'est adresse » est deja fait cote host-agent par JeV, qui
  est desormais fiable et prechauffe (ta lane precedente). N'ajoute AUCUN filtrage cote
  Presence : envoie le segment, le serveur tranche.
- Le PTT (mains libres OFF) doit rester rigoureusement identique. C'est le chemin de la
  demo de demain, il ne doit subir aucune regression.

## Tests — `dev/tests/test_ecoute_continue.py`
AUCUN peripherique reel : `PushToTalkCapture`/`CaptureContinue` acceptent une
`stream_factory` injectable, les tests existants s'en servent deja — reprends ce patron.
Fabrique des blocs int16 synthetiques (silence = zeros, parole = bruit d'amplitude connue).
Couvre au minimum :
- silence continu -> aucun segment
- parole puis 700 ms de silence -> exactement un segment, contenant la parole
- parole, silence court (300 ms), parole, puis 700 ms de silence -> UN SEUL segment
- salve de 100 ms puis silence -> aucun segment (sous le plancher de 400 ms)
- `suspendre()` pendant de la parole -> rien n'est accumule ; `reprendre()` repart propre
- segment de plus de 15 s -> coupe
- le comportement de `PushToTalkCapture` (start/stop) est inchange : garde un test qui
  le prouve

## Preuve a rendre
Ces tests ne dependent pas de tkinter, donc lance-les DANS le conteneur :

    docker exec mother-core-dev sh -c "cd /workspace && python -m pytest -q dev/tests/test_ecoute_continue.py"

Puis, comme `app.py` exige tkinter, lance la non-regression Presence sur l'HOTE Windows
(PowerShell, depuis `D:\BGB Training\MOTHER-dev`) :

    python -m pytest -q dev/tests/test_presence_premier_tour.py dev/tests/test_presence_stop_mains_libres.py dev/tests/test_presence_mains_libres.py dev/tests/test_presence_connexion_jev.py

Colle LES DEUX sorties telles quelles dans `nights/2026-09-20-OUT-ECOUTE-CONTINUE.md`,
avec le diff resume et les difficultes rencontrees. Ne reponds que OK.
