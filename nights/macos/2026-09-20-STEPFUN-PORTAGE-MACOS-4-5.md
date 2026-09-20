## 4. SPÉCIFICITÉS MACOS À TRAITER

### 4.1 — Permission micro (TCC)

macOS 10.14+ interdit tout accès au micro sans consentement utilisateur explicite, géré par le framework TCC (Transparency, Consent, and Control). PortAudio/sounddevice déclenchent ce contrôle à la première ouverture de flux.

**Déclaration de l'usage.** Pour un bundle `.app`, la chaîne affichée dans la boîte de dialogue vient de `NSMicrophoneUsageDescription` dans `Contents/Info.plist`. Sans cette clé, le système **tue le processus** au premier accès micro (sur versions récentes) ou affiche un message générique.

**Attribution du processus — le piège.** TCC identifie le « responsible process ». Or c'est le **host-agent** (pas l'UI tkinter) qui ouvre le flux. Si le host-agent est un script Python lancé par un `python3` hors bundle, le prompt peut être attribué à `python3` ou au terminal, pas à « Hyper Ambient ». Conséquences : chaîne de description ignorée, ré-autorisation demandée à chaque changement de binaire Python, bouton « Ouvrir les Réglages Système » inopérant. La voie sûre pour la distribution est d'**embarquer un Python signé dans le bundle** (PyInstaller, ou `python-build-standalone`). En phase 1 interne, accepter le prompt attribué à l'exécutable Python, mais le documenter.

**Détection du refus depuis Python.** Deux niveaux :

*Sans dépendance nouvelle* — tenter l'ouverture et intercepter l'erreur. C'est le seul test possible avec la pile actuelle (`sounddevice`/PortAudio). PortAudio remonte en principe une `PortAudioError` si TCC bloque, mais **le code d'erreur exact et le comportement (exception stricte vs. callback silencieux à zéros) ne sont pas vérifiés** — à valider sur Mac.

```python
# native/hostagent/macos_ttc_probe.py — sonde minimale, aucune dépendance
import sounddevice as sd

def micro_accessible() -> bool:
    """True si un flux d'entrée s'ouvre. Ne distingue pas 'pas de micro'
    de 'TCC refusé' — c'est le rôle de l'appelant via le message d'erreur."""
    try:
        with sd.InputStream(samplerate=48000, channels=1, dtype="int16"):
            return True
    except sd.PortAudioError as exc:
        print(f"[TCC?] ouverture micro refusée : {exc}", flush=True)
        return False
```

*Avec `pyobjc`* (dépendance lourde, à n'ajouter que si on vise la parité native complète — status item §4.3, overlay phase 2) — lecture de l'état d'autorisation sans déclencher le prompt :

```python
import AVFoundation
AVMediaTypeAudio = "soun"  # code 4 caractères attendu par AVFoundation
status = AVFoundation.AVCaptureDevice.authorizationStatusForMediaType_(AVMediaTypeAudio)
# 0 = NotDetermined, 1 = Restricted, 2 = Denied, 3 = Authorized
```

**Que faire côté produit au refus.** Le host-agent ne doit pas crasher (cf. `SystemExit(1)` actuel, réservé à l'absence de sounddevice). Il doit remonter un état métier `MICRO_POLICY` sur le canal existant vers l'UI Presence. L'UI affiche une bannière « Accès micro refusé » avec un bouton ouvrant les Réglages. L'ouverture se fait **côté UI**, pas côté host-agent (ADR-016 règle 2 interdit le spawn dans le host-agent) :

```python
# native/presence/app.py — ou ailleurs dans la couche UI
import subprocess, sys

def ouvrir_reglages_micro() -> None:
    if sys.platform == "darwin":
        subprocess.Popen([
            "open",
            "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone",
        ])
```

### 4.2 — Lanceur : du `.bat` au `.app`

**Phase 1 / dev interne : `.command`.** Un script shell exécutable, double-cliquable dans le Finder. Ouvre une fenêtre Terminal (acceptable en dev, gênant en prod). Remplaçant direct de `hyper-ambient.bat` :

```sh
#!/bin/sh
# native/presence/hyper-ambient.command
RES="$(cd "$(dirname "$0")" && pwd)"
export PYTHONPATH="$RES/../../src:$RES/../..:$PYTHONPATH"
exec /usr/bin/env python3 "$RES/app.py" "$@"
```

```bash
chmod +x native/presence/hyper-ambient.command
```

**Phase distribution : bundle `.app`.** Nécessaire pour l'icône, le nom propre, `NSMicrophoneUsageDescription`, la signature et la notarisation.

```
HyperAmbient.app/
└── Contents/
    ├── Info.plist
    ├── MacOS/
    │   └── hyper-ambient        # script shell launcher (ou binaire si PyInstaller)
    └── Resources/
        ├── hyper-ambient.icns
        ├── assets/
        ├── src/                 # code applicatif
        └── native/              # host-agent + presence
```

Launcher `Contents/MacOS/hyper-ambient` :

```sh
#!/bin/sh
RES="$(cd "$(dirname "$0")/../Resources" && pwd)"
export PYTHONPATH="$RES/src:$RES/native:$PYTHONPATH"
exec /usr/bin/env python3 "$RES/native/presence/app.py" "$@"
```

**Info.plist minimal** (`Contents/Info.plist`) :

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>fr</string>
    <key>CFBundleExecutable</key>
    <string>hyper-ambient</string>
    <key>CFBundleIdentifier</key>
    <string>com.hyperambient.presence</string>
    <key>CFBundleName</key>
    <string>HyperAmbient</string>
    <key>CFBundleDisplayName</key>
    <string>Hyper Ambient</string>
    <key>CFBundleIconFile</key>
    <string>hyper-ambient.icns</string>
    <key>CFBundleShortVersionString</key>
    <string>3.0.0</string>
    <key>CFBundleVersion</key>
    <string>3</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>NSMicrophoneUsageDescription</key>
    <string>Hyper Ambient utilise le micro pour la capture appuyer-pour-parler.</string>
    <key>LSUIElement</key>
    <false/>
</dict>
</plist>
```

`LSUIElement=true` ferait de l'app un agent sans icône Dock — pertinent si Presence devient pilotable uniquement par la barre de menus (§4.3). Garder `false` tant que la fenêtre tkinter est le point d'entrée principal.

### 4.3 — Icône barre de menus (NSStatusItem)

Windows a la barre des tâches ; macOS a la barre de menus. **tkinter n'expose aucune API pour créer un `NSStatusItem`.** Trois options, par ordre de coût croissant :

**Option A — renoncer en phase 1.** L'app reste une fenêtre Dock classique. Zéro dépendance. Acceptable si le produit ne repose pas sur un accès barre de menus.

**Option B — `rumps`.** Bibliothèque Python dédiée aux status bar apps. Dépend de `pyobjc`. Intégration avec tkinter délicate : `rumps.App.run()` installe sa propre boucle runloop Cocoa, incompatible avec `Tk.mainloop()` sur le même thread. Il faut lancer rumps dans un thread daemon et communiquer par `queue.Queue` :

```python
# native/presence/status_item.py — schéma d'intégration (non testé)
import queue, threading
import rumps

class StatusItem(rumps.App):
    def __init__(self, q: queue.Queue) -> None:
        super().__init__("Hyper Ambient", title="◈")
        self._q = q
        self.menu = [rumps.MenuItem("Quitter", callback=self._quit)]

    def _quit(self, _) -> None:
        self._q.put(("quit", None))

def demarrer(q: queue.Queue) -> None:
    threading.Thread(target=StatusItem(q).run, daemon=True).start()
```

**Risque assumé** : deux boucles événementielles (AppKit + Tk) cohabitant. Non vérifié.

**Option C — `pyobjc` direct** dans `native/presence/macos_overlay_native.py` (module déjà prévu en phase 2 §3.3). Si ce module existe, y créer le `NSStatusItem` évite une seconde dépendance de haut niveau. Justification de `pyobjc` : c'est la seule voie pour l'intégration Aqua native (status item, `NSPanel` overlay, états d'autorisation AVFoundation). Pour la phase 1 sans overlay natif, ne pas l'introduire.

### 4.4 — Signature et notarisation

Obligatoire uniquement si l'app est **distribuée à d'autres machines**. En dev local, une signature ad-hoc (`codesign -s -`) ou aucune signature suffit.

**Signature Developer ID** (hors App Store) :

```bash
codesign --force --options runtime \
  --sign "Developer ID Application: ÉQUIPE (TEAMID)" \
  --entitlements entitlements.plist \
  HyperAmbient.app
```

`--options runtime` (Hardened Runtime) est **obligatoire pour la notarisation**. Si on n'active pas le sandbox (choix recommandé phase 1 : le host-agent a besoin d'accès réseau sortant vers le conteneur et d'accès audio sans entrave), le fichier `entitlements.plist` peut être minimal ou vide.

Si le bundle contient des binaires non signés (`.so`, `.dylib` de PortAudio/sounddevice), ils doivent être signés **avant** le bundle, sinon le scellement échoue :

```bash
find HyperAmbient.app \( -name "*.so" -o -name "*.dylib" \) -print0 |
  while IFS= read -r -d '' f; do
    codesign --force --options runtime --sign "Developer ID Application: ÉQUIPE (TEAMID)" "$f"
  done
```

**Notarisation** (compte Apple Developer payant requis) :

```bash
ditto -c -k --keepParent HyperAmbient.app HyperAmbient.zip
xcrun notarytool store-credentials "HA_NOTARY" \
  --apple-id dev@exemple.com --team-id TEAMID --password <mot-de-passe-application>
xcrun notarytool submit HyperAmbient.zip --keychain-profile "HA_NOTARY" --wait
xcrun stapler staple HyperAmbient.app
```

Sans notarisation, Gatekeeper bloquera l'app sur tout Mac autre que celui de dev, même si elle est signée.

### 4.5 — Gatekeeper et quarantaine

Tout fichier téléchargé via navigateur, mail ou AirDrop reçoit l'attribut étendu `com.apple.quarantine`. Au premier lancement :

- **Non signée** : « HyperAmbient.app ne peut pas être ouvert car l'identité du développeur ne peut pas être confirmée. »
- **Signée, non notarisée** : « Apple n'a pas pu vérifier l'absence de logiciels malveillants » (variante selon version macOS).
- **Signée + notarisée** : passage direct.

Contournements utilisateur : clic droit → « Ouvrir » puis confirmation ; ou Réglages → Confidentialité et sécurité → « Ouvrir quand même ». Côté dev, retirer la quarantaine :

```bash
xattr -d com.apple.quarantine HyperAmbient.app
spctl --assess --type execute --verbose HyperAmbient.app   # diagnostic politique
```

Distribution interne par `scp`/partage réseau ne pose pas de quarantaine — voie la plus simple pour la recette.

---

## 5. RISQUES NON VÉRIFIÉS

Aucun de ces points n'a pu être testé faute de matériel. Ordre par risque décroissant.

### 5.1 — Attribution TCC et détection du refus micro

**Pourquoi c'est risqué.** Si le host-agent s'exécute via un `python3` hors bundle, le prompt TCC peut être attribué au mauvais exécutable : chaîne `NSMicrophoneUsageDescription` ignorée, autorisation non persistante, ou prompt réclamé à chaque mise à jour du binaire Python. Par ailleurs, le comportement exact de PortAudio sur refus TCC (exception `PortAudioError` explicite vs. callback muet à zéros) n'est pas documenté de manière fiable ; un callback silencieux ferait tourner l'app en mode « micro mort » sans erreur visible.

**Test.** Machine fraîche (jamais autorisée). Lancer le host-agent. Vérifier : (a) que la boîte de dialogue affiche bien la chaîne du `Info.plist` et le nom « Hyper Ambient » ; (b) refuser, puis relancer — le host-agent doit détecter le refus (via la sonde §4.1 ou l'état AVFoundation) et remonter `MICRO_POLICY` ; (c) réautoriser dans les Réglages et vérifier que la capture reprend sans redémarrage.

### 5.2 — Format et taux d'échantillonnage CoreAudio

**Pourquoi c'est risqué.** Le code actuel demande `dtype="int16"` et `SAMPLE_RATE` fixe. CoreAudio ne garantit ni le format ni le taux sur tous les devices (interfaces USB, AirPods, aggregation). PortAudio ne ré-échantillonne pas systématiquement : si le device refuse la combinaison, `sd.InputStream` lève une erreur, ou pire, certains backends ouvrent à un taux différent et désalignent le flux.

**Test.** Sur le Mac cible avec le micro de production :

```python
import sounddevice as sd
print(sd.query_devices())
print(sd.check_input_settings(device=None, samplerate=48000, channels=1, dtype="int16"))
```

Vérifier que tous les périphériques d'entrée réalistes acceptent `int16` + `SAMPLE_RATE`. Si non, prévoir une conversion/negotiation dans `platform_audio.py` (§2 déjà livrée — à réconcilier avec ce constat).

### 5.3 — Transparence et toujours-au-premier-plan de l'overlay

**Pourquoi c'est risqué.** Le chroma-key Windows (`-transparentcolor`) n'a pas d'équivalent Aqua. Le repli retenu (transparence globale de fenêtre) donne des coins carrés ou une bulle uniformément translucide, pas une découpe au pixel. Le comportement de `-topmost` et de `-alpha` diffère aussi selon la version de Tcl/Tk et selon que la fenêtre est une `Toplevel` ou un `NSPanel` natif.

**Test.** Lancer `overlay.py` sur le Mac. Vérifier : les coins sont-ils acceptables ? la bulle reste-t-elle au-dessus des fenêtres plein écran ? la souris traverse-t-elle les zones « transparentes » ? Comparer côte à côte avec Windows pour trancher si la phase 2 (`macos_overlay_native.py`, `NSPanel` + `NSWindow` non-activating) est obligatoire ou optionnelle.

### 5.4 — Cohabitation des boucles événementielles (status item + tkinter)

**Pourquoi c'est risqué.** Si on ajoute `rumps` ou `pyobjc` pour la barre de menus, deux boucles runloop tournent en parallèle (AppKit + Tk). Tk n'est pas thread-safe : tout appel tkinter depuis le thread AppKit peut corrompre l'état ou geler l'UI. Les patterns `after()` du code existant supposent une seule boucle.

**Test.** Intégrer un `NSStatusItem` minimal (menu « Quitter » + changement de titre). Cliquer 200 fois sur le menu pendant que l'overlay tourne. Vérifier : pas de freeze, pas de traceback Tk, arrêt propre de l'app depuis le menu.

### 5.5 — Notarisation et scellement des bibliothèques natives

**Pourquoi c'est risqué.** `notarytool` rejette silencieusement (ou avec un log cryptique) si le bundle contient du code non signé, des binaires modifiables, ou des liens symboliques vers l'extérieur. Les `.so`/`.dylib` de PortAudio embarquées par PyInstaller ou copiées à la main sont le cas d'échec classique.

**Test.** Signer puis soumettre à notarisation. Lire le log JSON en cas d'échec :

```bash
xcrun notarytool log <submission-id> --keychain-profile "HA_NOTARY"
```

Corriger jusqu'à `status: Accepted`, puis `stapler validate`.

### 5.6 — Comportements tkinter spécifiques Aqua

**Pourquoi c'est risqué.** `PhotoImage`/`iconphoto`, `wm attributes`, la résolution des chemins d'assets et le comportement de `after()` sous charge varient selon la version de Tcl/Tk livrée (python.org vs Homebrew vs système). Le code Windows utilise `iconbitmap` (`.ico`) — inopérant sur macOS — et `iconphoto` (PNG), dont le rendu Dock peut différer.

**Test.** Au démarrage de Presence sur le Mac :

```python
import tkinter as tk
print(tk.TkVersion)          # attendu 8.6.x
r = tk.Tk()
print(r.tk.call("tk", "windowingsystem"))  # attendu "aqua"
```

Vérifier que l'icône Dock apparaît, que `after(33, ...)` de l'overlay ne dérive pas (mesurer l'écart réel entre ticks), et qu'aucun `TclError` n'est levé sur les attributs de fenêtre.

### 5.7 — Résolution réseau hôte ↔ conteneur Docker

**Pourquoi c'est risqué.** Le cœur tourne en conteneur Docker Desktop ; le host-agent est sur l'hôte macOS. Le réseau Docker Desktop macOS passe par une VM (Virtualization.framework) : `localhost` depuis l'hôte ne joint pas toujours le conteneur comme sur Windows, et `host.docker.internal` se résout depuis le conteneur, pas depuis l'hôte. Selon le sens de la connexion (UDP 127.0.0.1 observé dans `overlay.py`), la topologie exacte doit être reconfirmée.

**Test.** Conteneur démarré. Depuis le host-agent sur le Mac, tester la joignabilité du point de terminaison exposé (`nc -zu <hôte> <port>`). Depuis le conteneur, vérifier `getent hosts host.docker.internal`. Documenter la topologie macOS retenue (port publié sur `127.0.0.1` vs `0.0.0.0`, ou socket partagé).

### 5.8 — Génération et rendu de l'icône `.icns`

**Pourquoi c'est risqué.** macOS exige un `.icns` multi-résolutions. `sips`/`iconutil` sont disponibles mais le rendu final (Dock, Finder, barre de titre) dépend de la présence des bonnes résolutions et d'un master 1024×1024 propre. Le code Windows fournit un `.ico` + un PNG 32 ; rien ne garantit que le master source soit en 1024.

**Test.** Générer le `.icns` (§4.3 commandes `sips`/`iconutil`), le placer dans `Resources/`, relancer le `.app`, vérifier le rendu dans le Dock, le Finder et la boîte de dialogue « Ouvrir avec ». Si le master n'est pas en 1024, le réexporter depuis la source vectorielle.