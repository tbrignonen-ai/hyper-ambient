# BRIEF Cursor — detection de voix par bande de frequences
Date : 2026-09-20 ~19h20. Lead technique : Claude (Opus).

## Le probleme, mesure en conditions reelles
Le mains libres declenche sur du bruit. `CaptureContinue` decide « c'est de la
parole » sur le seul RMS (energie large bande). Resultat observe ce soir, avec
des segments de 1,06 a 1,12 s envoyes a Whisper :

    TRANSCRIPT 'Realise par Neo035'
    TRANSCRIPT 'Realise par Neo035 Avec le soutien de SWIT Airsoft'
    TRANSCRIPT "l'ambiance"        <- l'utilisateur disait « Hyper ambient »

Les deux premieres sont des HALLUCINATIONS de Whisper : sur un segment court et
bruite, il recrache des generiques vus a l'entrainement. Chacune coute un
Whisper (GPU, ~100 W) et un appel JeV payant, pour du vent.

Demande explicite de l'utilisateur : « ca doit filtrer sur la bande de
frequences de la voix humaine, pour la early detection ».

## Perimetre STRICT
- `native/hostagent/windows_audio.py`
- `dev/tests/test_vad_bande_voix.py` (a creer)

INTERDIT : `native/presence/app.py`, `src/*`, `dev/scripts/*`, `.env.local`.
INTERDIT : lancer Presence, N'EXECUTE AUCUNE COMMANDE GIT.

## DESIGN IMPOSE

### 1. Critere spectral, en plus du RMS
Le RMS reste un pre-filtre (pas cher). Ajoute un second critere, evalue
seulement quand le RMS passe : l'energie doit etre concentree dans la bande de
la parole.

- Bande utile : environ 85 Hz a 3400 Hz (fondamentale voisee + formants).
- Calcule le rapport energie_bande / energie_totale par trame (une FFT reelle
  `numpy.fft.rfft` sur la trame suffit : 20 ms a 16 kHz = 320 echantillons,
  c'est negligeable en CPU).
- Une trame compte comme « parole » si ce rapport depasse un seuil expose en
  constante nommee et commentee (`RATIO_BANDE_VOIX`, commence a 0.60).
- Rejette ainsi : ventilateur et grave continu (sous 85 Hz), sifflements et
  cliquetis de clavier (au-dessus de 3400 Hz), souffle large bande.

### 2. Bonus si simple : stabilite de la fondamentale
Optionnel, ne complique pas si c'est lourd : la parole a une fondamentale qui
varie lentement, un bruit non. Si tu peux l'estimer a peu de frais (autocorrelation
sur la trame), exige qu'elle tombe entre 70 et 400 Hz. Si c'est trop couteux,
ignore ce point et dis-le dans l'OUT.

### 3. Duree minimale portee a 700 ms
Le plancher actuel est 400 ms. Whisper hallucine sous ~1 s. Porte le plancher a
700 ms, en constante nommee et commentee, en citant la mesure ci-dessus.

### 4. Ne casse rien
- `PushToTalkCapture` reste rigoureusement inchange (chemin de la demo).
- Les tests existants `dev/tests/test_ecoute_continue.py` doivent rester verts.
  S'ils fabriquent de la « parole » avec du bruit blanc, ils echoueront sur le
  nouveau critere spectral : corrige alors ces fixtures pour produire un signal
  VOISE realiste (somme de sinusoides a 150 Hz et ses harmoniques, enveloppe
  variable), et dis-le dans l'OUT. Ne desactive aucun test.

## Tests — `dev/tests/test_vad_bande_voix.py`
Signaux synthetiques, aucun peripherique. Couvre au minimum :
- sinusoide voisee 150 Hz + harmoniques, amplitude forte -> compte comme parole
- bruit blanc de meme RMS -> NE compte PAS comme parole
- sinusoide a 50 Hz (ventilateur) de meme RMS -> NE compte pas
- sinusoide a 6000 Hz (sifflement/clavier) de meme RMS -> NE compte pas
- silence -> ne compte pas
- segment voise de 500 ms -> rejete (sous le plancher de 700 ms)
- segment voise de 1200 ms suivi du silence -> un segment rendu

## Preuve
    docker exec mother-core-dev sh -c "cd /workspace && python -m pytest -q dev/tests/test_vad_bande_voix.py dev/tests/test_ecoute_continue.py"

Colle la sortie telle quelle dans `nights/2026-09-20-OUT-VAD-BANDE-VOIX.md`,
avec le diff resume et les difficultes. Ne reponds que OK.
