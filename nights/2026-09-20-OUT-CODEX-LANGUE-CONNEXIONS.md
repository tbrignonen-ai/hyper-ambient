# OUT — langue et connexions (20 septembre 2026)

Périmètre respecté : `dev/scripts/serve_hostagent.py`, `src/hostagent/`,
`dev/scripts/relance_hostagent.sh` et `dev/tests/`. Aucune modification sous
`native/presence/`, `src/i18n/` ou `src/onboarding/`.

## Résultat

La langue de l'assistante est désormais une opération unique :

| réglage | valeur sans accent | valeur avec accent explicite |
| --- | --- | --- |
| `HA_LANG` / `HYPER_AMBIENT_LANG` | langue choisie | langue choisie |
| `EARS_LANGUAGE` | langue choisie | langue choisie |
| `MOUTH_LANGUAGE` | langue choisie | `MOUTH_ACCENT` / `MOUTH_LANGUAGE_FORCE` |

`MOUTH_ACCENT` (et la force historique) est le signal volontaire : il permet,
par exemple, du texte français avec la phonétique anglaise. Une ancienne valeur
`MOUTH_LANGUAGE` seule n'est plus prise pour un accent, car elle était la cause
de la désynchronisation par défaut.

Le WebSocket accepte sur la session déjà ouverte :

```json
{"type":"options","language":"en"}
{"type":"options","language":"fr","accent":"en"}
```

Il répond `language_status`. Le bouton existant qui ne fait encore qu'écrire
`.env.local` est aussi couvert par une veille de 250 ms : elle applique la
nouvelle langue à la frontière du tour, sans redémarrer le processus.

Whisper/faster-whisper et Qwen3-ASR lisent leur attribut `language` à chaque
transcription ; Magpie transmet le sien à chaque synthèse. Ces trois changements
sont donc à chaud et les poids restent chargés. Pocket TTS charge des poids par
langue : il garde l'ancienne voix, retourne `state: reloading`, charge la
nouvelle instance en arrière-plan, puis l'échange entre deux tours. Piper et
Supertonic ne possèdent pas de carte de voix par langue dans cette configuration :
ils retournent `unsupported`, jamais un faux `ready`.

Enfin `GET /` du transport répond maintenant :

```json
{"status":"ready","transport":"hostagent"}
```

## Connexions — constats et cause racine

Le journal conteneur était sans ambiguïté sur l'échec de sonde :

```text
/tmp/hostagent.log:120-128  GET / HTTP/1.1" 404 Not Found (neuf fois)
/tmp/hostagent.log:132-137  GET / HTTP/1.1" 404 Not Found (six fois)
/tmp/hostagent.log:158-160  GET / HTTP/1.1" 404 Not Found (trois fois)
```

Ces sondes échouaient alors que le service traitait réellement les tours :
`/tmp/hostagent.log:139-145` contient `AUDIO_RECV`, transcription, premier audio
et réponse. La cause racine établie et corrigeable est donc l'absence de route
HTTP de disponibilité, pas l'ASR, Magpie ou le réseau audio.

Les coupures du journal hôte sont des redémarrages côté service, non des délais
de transcription :

```text
presence.log:604-606  AUDIO_SEND ... puis 1012 (service restart), sans "tour : terminé"
presence.log:747-755  options/jev_pret en 1012, puis quatre échecs de reconnexion
presence.log:1424-1426 AUDIO_SEND ... puis 1012, sans marqueur final
presence.log:1456-1458 même séquence, puis reconnexion à 1459
```

La preuve de l'effet utilisateur est directe : des tours normaux ont `AUDIO_SEND`
puis `tour : terminé` (`presence.log:1438-1440`, `1447-1449`), tandis que les
tours coupés par 1012 n'ont pas ce marqueur. La cause immédiate de ces coupures
est établie par le code de fermeture transmis par le pair : redémarrage du
service pendant le tour. L'initiateur externe n'est pas journalisé ;
`relance_hostagent.sh` écrase `/tmp/hostagent.log`, donc l'attribuer à une
personne ou à un superviseur serait une invention. La route de sonde supprime
l'échec 404 avéré. La nouvelle bascule de langue ne relance plus le service :
elle passe par le WS ou la veille `.env.local`.

Je n'ai trouvé ni timeout EARS/BRAIN, ni exception de tour dans le journal
conteneur conservé. Le journal est écrasé par `relance_hostagent.sh`, donc il ne
contient pas les processus précédents ; l'attribution des 1012 provient des
lignes hôte citées ci-dessus, et la cause de sonde est établie par les 404
conteneur cités.

## Preuve TDD — échec avant, succès après

Avant les corrections, exactement les nouveaux scénarios échouaient ainsi :

```text
$ docker exec mother-core-dev python -m pytest dev/tests/test_hostagent_transport.py::test_la_sonde_http_racine_confirme_que_le_transport_est_pret dev/tests/test_taquet_wire2.py::test_langue_assistante_synchronise_oreille_cerveau_et_bouche dev/tests/test_taquet_wire2.py::test_accent_explicite_survit_au_changement_de_langue -q
FFF                                                                      [100%]
=================================== FAILURES ===================================
_________ test_la_sonde_http_racine_confirme_que_le_transport_est_pret _________
E       assert 404 == 200
_________ test_langue_assistante_synchronise_oreille_cerveau_et_bouche _________
E       AttributeError: module 'serve_hostagent_env_local' has no attribute 'synchroniser_langue_assistante'
_____________ test_accent_explicite_survit_au_changement_de_langue _____________
E       AttributeError: module 'serve_hostagent_env_local' has no attribute 'synchroniser_langue_assistante'
=========================== short test summary info ============================
FAILED dev/tests/test_hostagent_transport.py::test_la_sonde_http_racine_confirme_que_le_transport_est_pret
FAILED dev/tests/test_taquet_wire2.py::test_langue_assistante_synchronise_oreille_cerveau_et_bouche
FAILED dev/tests/test_taquet_wire2.py::test_accent_explicite_survit_au_changement_de_langue
3 failed, 1 warning in 0.77s
```

Après correction, la suite ciblée (sonde, protocole WS, synchronisation,
accent et script de relance) passe :

```text
$ docker exec mother-core-dev python -m pytest dev/tests/test_hostagent_transport.py dev/tests/test_taquet_wire2.py dev/tests/test_carte_figee.py -q
.............................                                            [100%]
29 passed, 23 warnings in 0.80s
```

## Vérification finale — sortie intégrale

Commande exécutée :

```text
docker exec mother-core-dev python -m pytest dev/tests -q --ignore=dev/tests/test_health_sondes.py
```

```text
.........................................ssssss......................... [  4%]
........................................................................ [  9%]
.............................................................s.......... [ 14%]
........................................................................ [ 19%]
........................................................................ [ 24%]
............................................................x......x.... [ 28%]
........................................................................ [ 33%]
..............ss........................................................ [ 38%]
.sss..............sssssFss.Fs...s................sssssssssss............ [ 43%]
....sssssssssss...sssss...sssss.sss..................................... [ 48%]
........................................................................ [ 52%]
........................................................................ [ 57%]
...............................................................Fs....F.. [ 62%]
........................................................................ [ 67%]
........................................................................ [ 72%]
........................................................................ [ 76%]
........................................................................ [ 81%]
........................................................................ [ 86%]
........................................................................ [ 91%]
........................................................................ [ 96%]
............................................................             [100%]
=================================== FAILURES ===================================
________________________ test_orbe_repos_reste_lisible _________________________

    def test_orbe_repos_reste_lisible():
>       from native.presence import overlay as visuel

dev/tests/test_presence_onboarding.py:393:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    """Présence visuelle d'hyper-ambient : une bulle qui respire, pas une fenêtre.
    
    Le dessin vit sur l'hôte Windows — le conteneur n'a aucun accès à l'écran.
    tkinter seulement : l'utilisateur a refusé PyQt, Electron et pygame.
    
        python native/presence/overlay.py --demo
        python native/presence/overlay.py --coin haut-gauche --taille 160
        python native/presence/overlay.py --off --port 8123
    """
    from __future__ import annotations
    
    import argparse
    import json
    import math
    import socket
    import sys
    import time
>   import tkinter as tk
E   ModuleNotFoundError: No module named 'tkinter'

native/presence/overlay.py:18: ModuleNotFoundError
___________ test_un_appui_deja_relache_est_invisible_pour_la_boucle ____________

    def test_un_appui_deja_relache_est_invisible_pour_la_boucle():
        """Un PTT terminé avant ``_boucle_tours`` ne démarre pas le micro.
    
        C'est la mécanique du premier tour perdu : l'Event ne file pas les
        pulses. Après le correctif UI, ce chemin n'est plus joignable depuis
        le bouton (l'appui est refusé tant que le canal n'est pas prêt).
        """
>       from native.presence.app import SessionVocale

dev/tests/test_presence_premier_tour.py:52:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    """Application fenêtrée d'hyper-ambient : appuyer-pour-parler, sans terminal.
    
    Le moteur (poignée de main, micro, restitution) vit déjà dans
    ``native/hostagent/talk.py``. Le dessin de la bulle vit déjà dans
    ``native/presence/overlay.py``. Ce fichier n'ajoute que le cadre : une
    fenêtre tkinter *normale* (barre de titre, croix), un bouton qu'on
    maintient, et le relais vers l'interface par une file — tkinter n'est
    pas sûr entre fils, donc le réseau et l'audio ne touchent jamais un
    widget.
    
        python native/presence/app.py
    """
    from __future__ import annotations
    
    import argparse
    import json
    import math
    import os
    import queue
    import sys
    import threading
    import time
    import ctypes
>   import tkinter as tk
E   ModuleNotFoundError: No module named 'tkinter'

native/presence/app.py:24: ModuleNotFoundError
_______________ test_assurer_stdio_pythonw_ecrit_dans_un_journal _______________

    def test_assurer_stdio_pythonw_ecrit_dans_un_journal(tmp_path: Path):
>       assert termine.returncode == 0, termine.stderr
E       AssertionError: Traceback (most recent call last):
E           File "/tmp/pytest-of-root/pytest-114/test_assurer_stdio_pythonw_ecr0/probe_stdio.py", line 4, in <module>
E             from native.presence.app import assurer_stdio
E           File "/workspace/native/presence/app.py", line 24, in <module>
E             import tkinter as tk
E         ModuleNotFoundError: No module named 'tkinter'

E       assert 1 == 0
E        +  where 1 = CompletedProcess(args=['/usr/bin/python', '/tmp/pytest-of-root/pytest-114/test_assurer_stdio_pythonw_ecr0/probe_stdio....\/presence/app.py", line 24, in <module>\n    import tkinter as tk\nModuleNotFoundError: No module named \'tkinter\'\n').returncode

dev/tests/test_taquet_produit.py:71: AssertionError
________________ test_palettes_a11y_respectent_wcag_non_textuel ________________

    def test_palettes_a11y_respectent_wcag_non_textuel():
>       from native.presence.overlay import FOND_CHAMP, palettes

dev/tests/test_taquet_produit.py:152:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

    """Présence visuelle d'hyper-ambient : une bulle qui respire, pas une fenêtre.
    
    Le dessin vit sur l'hôte Windows — le conteneur n'a aucun accès à l'écran.
    tkinter seulement : l'utilisateur a refusé PyQt, Electron et pygame.
    
        python native/presence/overlay.py --demo
        python native/presence/overlay.py --coin haut-gauche --taille 160
        python native/presence/overlay.py --off --port 8123
    """
    from __future__ import annotations
    
    import argparse
    import json
    import math
    import socket
    import sys
    import time
>   import tkinter as tk
E   ModuleNotFoundError: No module named 'tkinter'

native/presence/overlay.py:18: ModuleNotFoundError
=============================== warnings summary ===============================
dev/tests/test_debit.py::test_etirement_allonge_la_duree
  /usr/lib/python3/dist-packages/pkg_resources/_vendor/pyparsing.py:87: DeprecationWarning: module 'sre_constants' is deprecated
    import sre_constants

dev/tests/test_hostagent_rapport.py::test_le_rapport_arrive_apres_la_premiere_trame_audio
  /usr/local/lib/python3.11/dist-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.

dev/tests/test_hostagent_rapport.py: 5 warnings
dev/tests/test_hostagent_transport.py: 11 warnings
  /usr/local/lib/python3.11/dist-packages/anyio/_backends/_asyncio.py:665: DeprecationWarning: Passing 'msg' argument to Task.cancel() is deprecated since Python 3.11, and scheduled for removal in Python 3.14.

dev/tests/test_hostagent_rapport.py: 5 warnings
dev/tests/test_hostagent_transport.py: 11 warnings
  /usr/local/lib/python3.11/dist-packages/anyio/_backends/_asyncio.py:665: DeprecationWarning: Passing 'msg' argument to Future.cancel() is deprecated since Python 3.11, and scheduled for removal in Python 3.14.

dev/tests/test_integration.py::test_gate_permission
  /workspace/dev/tests/test_integration.py:86: DeprecationWarning: Gate.can_execute is deprecated and will be removed in a future version. Use Gate.check instead.
    assert gate.can_execute("test_action")

dev/tests/test_integration.py::test_gate_permission
  /workspace/dev/tests/test_integration.py:89: DeprecationWarning: Gate.can_execute is deprecated and will be removed in a future version. Use Gate.check instead.
    assert not gate_plan.can_execute("test_action")

dev/tests/test_integration.py::test_gate_permission
  /workspace/dev/tests/test_integration.py:92: DeprecationWarning: Gate.can_execute is deprecated and will be removed in a future version. Use Gate.check instead.
    assert not gate_yolo.can_execute("test_action")

dev/tests/test_stepfun.py::test_stepfun_init
dev/tests/test_stepfun.py::test_stepfun_init
  /usr/local/lib/python3.11/dist-packages/anyio/_backends/_asyncio.py:618: DeprecationWarning: Passing 'msg' argument to Task.cancel() is deprecated since Python 3.11, and scheduled for removal in Python 3.14.

dev/tests/test_stepfun.py::test_stepfun_init
dev/tests/test_stepfun.py::test_stepfun_init
  /usr/local/lib/python3.11/dist-packages/anyio/_backends/_asyncio.py:618: DeprecationWarning: Passing 'msg' argument to Future.cancel() is deprecated and will be removed in Python 3.14.

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED dev/tests/test_presence_onboarding.py::test_orbe_repos_reste_lisible
FAILED dev/tests/test_presence_premier_tour.py::test_un_appui_deja_relache_est_invisible_pour_la_boucle
FAILED dev/tests/test_taquet_produit.py::test_assurer_stdio_pythonw_ecrit_dans_un_journal
FAILED dev/tests/test_taquet_produit.py::test_palettes_a11y_respectent_wcag_non_textuel
4 failed, 1437 passed, 61 skipped, 2 xfailed, 41 warnings in 18.12s
```

Les quatre échecs sont tous l'absence de `tkinter` dans le conteneur et sont
sous `native/presence/`, zone expressément interdite ici. Aucun échec nouveau
ne vient de la langue, du transport ou de la sonde.
