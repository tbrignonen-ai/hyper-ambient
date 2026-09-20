---
date: 2026-09-20
heure: ~20h45 Europe/Paris
type: out
lane: PORTAGE-MACOS
auteur: Qwen Code
related: ["[[2026-09-20-BRIEF-QWEN-MACOS]]", "[[2026-09-20-STEPFUN-PORTAGE-MACOS]]", "[[2026-09-20-STEPFUN-PORTAGE-MACOS-SUITE]]", "[[2026-09-20-STEPFUN-PORTAGE-MACOS-4-5]]"]
---

# OUT Qwen — fichiers du portage macOS

Périmètre respecté : **5 fichiers créés, aucun fichier existant modifié**.
`native/hostagent/windows_audio.py`, `native/presence/app.py`,
`native/presence/overlay.py`, `src/*`, `dev/scripts/*`, `.env.local` non touchés
(vérifié par horodatage : les trois premiers portent des mtime antérieures à mon
premier écrit, 19:12 / 19:49 / 10:40 contre 19:55→20:07 pour mes fichiers).
Aucune commande git exécutée.

Le chemin Windows de la démonstration est intact : sur Windows,
`platform_audio` **est** `windows_audio` (identité des objets, pas des copies),
et rien n'importe encore `platform_audio` — voir « Reste à câbler ».

## Fichiers créés

| Fichier | Rôle |
|---|---|
| `native/hostagent/platform_audio.py` | Abstraction plateforme de la capture audio (Windows délègue, macOS/Linux via CoreAudio) |
| `native/presence/platform_ui.py` | Gardes des `ctypes.windll` d'`app.py`/`overlay.py` + équivalents macOS |
| `packaging/macos/Info.plist` | Bundle `.app`, dont `NSMicrophoneUsageDescription` |
| `packaging/macos/lancer.command` | Lanceur macOS, équivalent de `hyper-ambient.bat` |
| `dev/tests/test_platform_audio.py` | 15 tests qui passent sur Windows |

## Pytest — preuve demandée, sortie telle quelle

```
$ python -m pytest -q dev/tests/test_platform_audio.py
...............                                                          [100%]
15 passed in 0.09s
```

Non-régression audio (les tests existants du chemin Windows, inchangés) :

```
$ python -m pytest -q dev/tests/test_platform_audio.py dev/tests/test_windows_audio.py dev/tests/test_ecoute_continue.py dev/tests/test_vad_bande_voix.py
....................................                                     [100%]
36 passed in 0.55s
```

## Ce que contient chaque fichier

### `native/hostagent/platform_audio.py`

API publique identique sur les deux OS : `PushToTalkCapture`,
`CaptureContinue`, `frames_from_samples`, `lister_peripheriques_entree`
(plus `AudioFrame`, `FRAME_SAMPLES`, `SAMPLE_RATE` ré-exportés, et
`API_PUBLIQUE` qui écrit le contrat noir sur blanc).

- **Windows** : ré-exports purs de `windows_audio` — y compris
  `lister_peripheriques_entree = _lister_peripheriques_entree` et
  `_fabrique_flux = _default_stream_factory`. La branche ne contient
  **que** des `ImportFrom` (pincé par un test AST).
- **macOS / Linux** : mêmes classes, par **héritage** de `windows_audio`,
  avec une fabrique de flux CoreAudio (`sd.InputStream`, 16 kHz / mono /
  int16, import paresseux) et une traduction d'erreur
  `ErreurMicroIndisponible` portant la piste TCC.
- `micro_accessible()` : sonde d'ouverture du micro (étude §4.1), rend
  `False` sans lever — de quoi remonter un état métier vers Presence au
  lieu de crasher.

### `native/presence/platform_ui.py`

Aucun `ctypes.windll` au niveau module : `ctypes` n'est importé qu'à
l'intérieur de `_workarea_windows()` et `force_win32_window_icon()`, toutes
deux derrière `IS_WINDOWS`. Vérifié en chargeant le fichier avec
`sys.platform` forcé à `darwin` puis `linux` : `hasattr(module, "windll")`
est `False` dans les deux cas, aucune fonction ne lève.

Fonctions (noms alignés sur l'étude pour que ses diffs §3.1/§3.2
s'appliquent tels quels) : `set_app_identity`, `apply_window_icon`,
`force_win32_window_icon`, `apply_overlay_window_mode` → `"chromakey"` |
`"alpha"` | `"opaque"`, `screen_workarea`, plus deux ajouts assumés
(`aire_utile`, `fond_canvas_pour_mode`, voir écarts).

### `packaging/macos/Info.plist`

Celui de l'étude §4.2, à l'identique, avec `NSMicrophoneUsageDescription`
(chaîne élargie : appuyer-pour-parler **et** écoute continue mains libres,
les deux consomment le micro). Validé ici avec `plistlib` : XML bien formé,
11 clés, dont `CFBundleIdentifier = com.hyperambient.presence`.

### `packaging/macos/lancer.command`

`#!/bin/sh`, résout la racine depuis son propre emplacement
(`packaging/macos/../..`), pose `PYTHONPATH`, `cd` à la racine puis
`exec "$INTERPRETEUR" -u native/presence/app.py "$@"` — même forme que le
`.bat` (qui fait `cd /d` + `start pythonw`). `HYPERAMBIENT_PYTHON` permet de
viser un interpréteur précis : le `python3` système n'a pas toujours
tkinter 8.6 ni sounddevice, et c'est lui qui recevra la permission TCC.
Vérifié : **0 octet CR** (fins de ligne LF — un `.command` en CRLF ne
démarre pas), et `bash -n` (WSL) rend la syntaxe valide.

### `dev/tests/test_platform_audio.py`

15 tests, sans périphérique audio ni `sounddevice` (fabrique de flux
injectée, patron de `test_windows_audio.py` / `test_ecoute_continue.py`) :

- le fichier compile (`py_compile`) ; aucun import de `sounddevice` au
  niveau module ; la branche Windows ne fait que ré-exporter (test AST) ;
- API publique complète + surface mains libres utilisée par `app.py`
  (`segment_pret`, `prendre_segment`, `suspendre`, `reprendre`, `forcer_fin`) ;
- **délégation Windows par identité** des 4 noms + fabrique de flux, et
  50 trames float32 de 320 échantillons à travers l'abstraction ;
- **branche macOS réellement exécutée depuis Windows** : le module est
  rechargé avec `sys.platform = "darwin"`, ce qui permet de vérifier
  l'héritage (`issubclass`), la fabrique de flux distincte, le découpage
  en trames, le VAD qui segmente 800 ms de parole puis 700 ms de silence,
  la branche Linux, un refus CoreAudio traduit en erreur actionnable
  (cause préservée, piste TCC présente, `micro_accessible()` → `False`),
  les paramètres du flux (16000 / 1 / int16), et le message « sounddevice
  absent » qui ne parle plus de Windows.

## Écarts assumés avec l'étude

1. **La branche POSIX hérite au lieu de recopier.** L'étude §2 esquisse une
   réécriture complète (`_dernier_stamp`, `_next_stamp`, …). Elle a été
   écrite sur un `windows_audio.py` de 181 lignes ; le fichier en fait
   aujourd'hui ~380 (VAD bande-voix, `CaptureContinue`, seuil calibré).
   Recopier aurait produit **deux VAD qui divergent** — exactement le fork
   que `CONSIGNE-PORTAGE-MACOS` interdit. Or `windows_audio` est déjà
   portable : aucun `ctypes`, numpy/`time`/`threading`/`os`, `sounddevice`
   importé à l'intérieur des fonctions. Il s'importe donc sur macOS, et on
   lui prend la logique ; seuls la fabrique de flux et les messages
   diffèrent. Conséquence : le nom « windows_audio » apparaît sur macOS
   (nom trompeur, déjà relevé par l'inventaire §1).
2. **L'étude omettait `CaptureContinue`** de la liste à déléguer (rédigée
   avant l'écoute continue). Elle est dans l'API publique, sur les deux
   branches, et testée.
3. **Les deux fichiers d'étude sont tronqués dans le dépôt.**
   `…PORTAGE-MACOS.md` s'arrête à la ligne 74 au milieu de `_next_stamp`
   (`maintenant`), `…PORTAGE-MACOS-SUITE.md` à la ligne 579 au milieu de
   `MacNativeOverlay` (`# -- coordonnées : Cocoa`). J'ai écrit la suite
   moi-même à partir du code réel ; le sketch §3.0 de `platform_ui` était,
   lui, complet.
4. **`screen_workarea` rend `(x, y, w, h)`** comme l'étude, mais
   `overlay.aire_utile` attend `(gauche, haut, droite, bas)`. Les deux sont
   livrés : `aire_utile(racine)` est le remplaçant direct du bloc
   `windll.user32.SystemParametersInfoW` de l'overlay, à la différence
   près qu'il ne rend jamais `None`.
5. **Assets icône** : l'étude demande `hyper-ambient-256.png` et
   `-128.png`, qui n'existent pas. `assets/` contient
   `hyper-ambient.png` (**256×256**, le master), `-48.png`, `-32.png`,
   `hyper-ambient.ico` et des `_tmp_*.png`. Les candidats macOS listent les
   deux noms attendus *puis* le master réel : les absents sont filtrés par
   `is_file()`, donc générer les PNG de l'étude plus tard les fera prendre
   automatiquement, sans retoucher le code.
6. **Bug corrigé dans le sketch §3.0** : `tk.PhotoImage(file=…)` sans
   `master` lève `RuntimeError: Too early to create image` quand aucune
   racine par défaut n'existe, et le `except (OSError, tk.TclError)` du
   sketch ne l'attrape pas — il violait son propre contrat « aucune
   fonction ne lève ». Corrigé : `master=root` explicite, `RuntimeError`
   capturée, filet extérieur large sur un chemin purement cosmétique.
   Reproduit ici, donc pas une hypothèse.
7. **Ajouts au-delà des 4 noms imposés** (tous justifiés par l'étude) :
   `ErreurMicroIndisponible` + `micro_accessible()` (§4.1, la sonde était
   prévue dans un fichier `macos_ttc_probe.py` **hors périmètre** — repliée
   ici pour ne pas créer de 6e fichier), `fond_canvas_pour_mode` (§3.2.2,
   évite le bug « peindre `#010203` en mode alpha ne gomme rien »),
   `aire_utile` (écart 4), `API_PUBLIQUE`, `EST_WINDOWS`/`EST_MACOS`,
   `HAUTEUR_BARRE_MENUS_MACOS`.
8. **Non fourni volontairement** : `ouvrir_reglages_micro()` (§4.1) —
   c'est un `subprocess.Popen` côté UI, hors du périmètre de fichiers du
   brief ; `macos_overlay_native.py` (§3.3) — phase 2, dépendance pyobjc,
   hors périmètre ; `status_item.py` (§4.3) — option B/C, hors périmètre.

**Dépendances : aucune nouvelle.** `numpy` et `sounddevice` sont déjà la
pile du host-agent. `Cocoa`/pyobjc reste strictement optionnel : absent,
`screen_workarea` retombe sur l'estimation Tk (écran moins 24 pt).

## Vérifié ici, sur l'hôte Windows

- `pytest` : 15/15, et 36/36 avec les tests audio existants.
- `platform_ui` chargé avec `sys.platform` forcé à `darwin` puis `linux` :
  API complète, pas de `windll`, `apply_overlay_window_mode` rend `alpha`
  (appels `overrideredirect`, `-topmost`, `-alpha 0.97`) et `opaque` sur
  Linux, `screen_workarea` rend l'estimation `(0, 24, 1512, 958)` sans
  pyobjc, rien ne lève sur une racine factice ou `None`.
- `platform_ui` sur une **vraie racine Tk Windows** : `apply_window_icon`
  charge le PNG 32×32, garde la référence anti-GC, `force_win32_window_icon`
  et `screen_workarea` s'exécutent sans exception — `(0, 0, 2560, 1392)`,
  barre des tâches de 48 px bien exclue.
- `Info.plist` : XML bien formé, clés présentes (`plistlib`).
- `lancer.command` : 0 octet CR, syntaxe valide (`bash -n`), chemin
  `native/presence/app.py` exact depuis `packaging/macos/../..`.
- `py_compile` sur les deux modules Python.

## NON vérifiable sans Mac — à tester sur matériel réel

Rien de ce qui suit n'a été exécuté sur macOS. Ordre par risque.

1. **TCC, forme du refus.** Si PortAudio bloque sur une permission refusée
   en livrant un callback muet à zéros au lieu de lever, `micro_accessible()`
   répond `True` et l'app tourne en micro mort sans erreur visible
   (`_fabrique_flux` n'attrape que les exceptions). *Test* : machine
   fraîche, lancer le host-agent, vérifier que la boîte de dialogue affiche
   la chaîne du `Info.plist` et « Hyper Ambient » ; refuser, relancer,
   vérifier que le refus est détecté ; réautoriser et vérifier la reprise
   sans redémarrage.
2. **Attribution TCC du « responsible process ».** Avec `lancer.command`,
   l'exécutable est un `python3` hors bundle : le prompt peut être attribué
   au terminal ou à l'interpréteur, la chaîne `NSMicrophoneUsageDescription`
   ignorée, et l'autorisation redemandée à chaque changement de binaire.
   *Le `Info.plist` livré ne sert à rien tant qu'aucun bundle `.app`
   n'existe.* La voie sûre reste un Python signé embarqué (étude §4.1).
3. **Format / taux CoreAudio.** `int16` + 16 kHz imposés au device :
   PortAudio ne ré-échantillonne pas systématiquement. Soit
   `sd.InputStream` lève (auquel cas `ErreurMicroIndisponible`), soit
   certains backends ouvrent à un autre taux et désalignent le flux —
   `frames_from_samples` ne s'en apercevrait pas. *Test* :
   `sd.check_input_settings(device=None, samplerate=16000, channels=1, dtype="int16")`
   sur chaque périphérique réaliste (micro intégré, USB, AirPods, agrégat).
4. **Tk Aqua.** `-alpha` accepté et rendu à 0.97 ; `-topmost` fiable ou non
   selon les Spaces, le plein écran, Mission Control ; `iconphoto` PNG
   (exige Tk 8.6 — le Tk 8.5 du Python système macOS ne lit pas le PNG dans
   `PhotoImage`, et `apply_window_icon` retournerait `None` en silence) ;
   dérive du `after(33, …)` de l'overlay. *Test* : `tk.TkVersion` et
   `r.tk.call("tk", "windowingsystem")` attendus `8.6.x` / `aqua`.
5. **Transparence de l'overlay, non-parité assumée.** Le mode `"alpha"`
   donne une bulle uniformément translucide à coins carrés, pas une découpe
   au pixel : les zones « transparentes » ne laissent pas passer la souris
   comme le chroma-key Windows. *Test* : comparer côte à côte avec Windows
   et trancher si la phase 2 (`NSWindow` via pyobjc, étude §3.3) devient
   obligatoire.
6. **`NSScreen.visibleFrame` via pyobjc.** Conversion Cocoa (origine
   bas-gauche) → Tk (haut-gauche) non exécutée ; comportement multi-écran
   inconnu (`mainScreen()` n'est pas forcément l'écran portant l'overlay) ;
   sans pyobjc l'estimation à 24 pt **n'exclut pas le Dock**.
7. **Callback temps réel.** Le `print(…, flush=True)` hérité de
   `windows_audio._on_audio` (chemin PTT) peut pénaliser la latence sur un
   fil temps réel macOS. Inchangé volontairement : c'est du code Windows en
   production ce soir.
8. **`lancer.command` en conditions réelles.** Double-clic Finder, bit
   exécutable à reposer sur le Mac (`chmod +x packaging/macos/lancer.command`
   — un transfert depuis Windows ne le conserve pas forcément), quarantaine
   Gatekeeper sur un fichier reçu par navigateur/AirDrop, et quel `python3`
   est résolu (tkinter **et** sounddevice doivent y exister).
9. **`Info.plist` non validé par les outils Apple.** `plutil -lint` non
   exécuté (validation `plistlib` seulement). `CFBundleIconFile` pointe vers
   `hyper-ambient.icns`, **qui n'existe pas** ; le master PNG actuel est en
   256 px, pas en 1024 (étude §5.8).
10. **Hors de ce qui a été écrit** : rendu audio (haut-parleur, chemin
    `talk.py`) — le brief ne demandait que la capture ; réseau hôte macOS ↔
    conteneur Docker (étude §5.7) ; signature et notarisation (§4.4).

## Reste à câbler (interdit ici : fichiers hors périmètre)

`platform_audio.py` et `platform_ui.py` sont créés mais **rien ne les
importe encore** — le câblage touche des fichiers interdits par le brief.
Quand la démonstration sera passée :

- `native/presence/app.py:551` — `from native.hostagent.windows_audio import CaptureContinue` → `platform_audio`.
- `native/hostagent/talk.py:20` — `PushToTalkCapture` → `platform_audio`.
- `dev/scripts/verify_hostagent_loop.py:24` et `dev/scripts/_probe_client.py:29` — `frames_from_samples`.
- `native/presence/app.py` — appliquer le diff §3.1 de l'étude
  (`set_app_identity`, `apply_window_icon`, `_appliquer_icone_win32` réduit à
  `force_win32_window_icon`) ; les noms livrés sont ceux du diff.
- `native/presence/overlay.py` — appliquer §3.2 : retirer
  `from ctypes import Structure, byref, c_long` et le `try: from ctypes import windll`,
  remplacer `aire_utile` local par `platform_ui.aire_utile` (même contrat
  `(gauche, haut, droite, bas)`, jamais `None`), passer la configuration de
  fenêtre par `apply_overlay_window_mode`, **et** remplacer chaque
  `COULEUR_TRANSPARENTE` de fond/gomme par `fond_canvas_pour_mode(mode, FOND_CHAMP)`
  (lignes 630, 634, 645, 694 et le dessin). Attention : `overlay.py` remet
  `-alpha` à 1.0 ligne 637 — cet appel annulerait le repli macOS et doit
  sauter dans le mode `"alpha"`.
- Assets : générer `hyper-ambient.icns` (+ idéalement `-256.png`/`-128.png`)
  depuis le master ; `chmod +x packaging/macos/lancer.command`.
