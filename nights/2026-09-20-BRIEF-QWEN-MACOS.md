# BRIEF Qwen Code — ecrire les fichiers du portage macOS
Lead : Claude (Opus). 2026-09-20 ~20h30.

## Contexte
hyper-ambient est un assistant vocal developpe sur Windows. Objectif : preparer
le portage macOS. Une etude a deja ete produite et validee, elle contient
l'inventaire, les gardes de plateforme et la solution pour la transparence de
l'overlay. ELLE EST TA SOURCE, lis-la en entier avant d'ecrire :

  nights/macos/2026-09-20-STEPFUN-PORTAGE-MACOS.md        (inventaire)
  nights/macos/2026-09-20-STEPFUN-PORTAGE-MACOS-SUITE.md  (gardes + overlay)
  nights/macos/2026-09-20-STEPFUN-PORTAGE-MACOS-4-5.md    (specificites macOS)

## Ta mission : ECRIRE LE CODE, pas des recommandations
Materialise l'etude en fichiers reels, compilables, dans le depot.

A produire :
1. `native/hostagent/platform_audio.py` — abstraction plateforme de la capture
   audio. Sur Windows elle DELEGUE a `native/hostagent/windows_audio.py`
   INCHANGE. Sur macOS/Linux, CoreAudio via sounddevice. Meme API publique :
   `PushToTalkCapture`, `CaptureContinue`, `frames_from_samples`,
   `lister_peripheriques_entree`.
2. `native/presence/platform_ui.py` — gardes des appels `ctypes.windll` de
   `app.py` et `overlay.py`, avec l'equivalent macOS quand il existe (icone,
   zone de travail de l'ecran, identifiant d'application, transparence).
3. `packaging/macos/Info.plist` — avec `NSMicrophoneUsageDescription`.
4. `packaging/macos/lancer.command` — lanceur equivalent a
   `native/presence/hyper-ambient.bat`.
5. `dev/tests/test_platform_audio.py` — tests qui passent SUR WINDOWS :
   verifient que l'abstraction delegue bien a l'implementation Windows, que
   l'API publique est complete, et que le module macOS s'importe sans erreur de
   syntaxe (compile, meme s'il ne peut pas s'executer ici).

## Contraintes absolues
- NE MODIFIE PAS `native/hostagent/windows_audio.py`, `native/presence/app.py`,
  `native/presence/overlay.py`, `src/*`, `dev/scripts/*`, `.env.local`.
  Tu CREES des fichiers neufs. Le chemin Windows doit rester intact : c'est
  celui d'une demonstration imminente.
- Aucun environnement macOS pour tester : signale explicitement, en fin de
  rapport, chaque point que tu n'as pas pu verifier.
- Python 3.11+. Pas de dependance nouvelle sans la justifier.
- N'EXECUTE AUCUNE COMMANDE GIT.

## Preuve
    python -m pytest -q dev/tests/test_platform_audio.py
(sur l'hote Windows, depuis D:\BGB Training\MOTHER-dev)

Rapport dans `nights/macos/2026-09-20-OUT-QWEN-PORTAGE.md` : liste des fichiers
crees, sortie pytest telle quelle, et les points non verifiables sur Mac.
