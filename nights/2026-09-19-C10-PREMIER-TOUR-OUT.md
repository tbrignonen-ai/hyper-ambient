---
date: 2026-09-19
type: out
lane: C10
cible: bug « premier tour sans réponse »
---

# C10 OUT — Premier tour souvent sans réponse

CPU / Presence hôte. llama-server non touché. `.env.local` non touché. Pas de git.
Host-agent **non relancé** : pas de section « GPU » dans `nights/2026-09-19-C9-MAGPIE-OUT.md` (consigne).

## Cause prouvée (avant correctif)

**Hypothèse 1 — PTT avant ouverture WebSocket.** Prouvée.

Mécanisme, lu dans le code puis pincé par test :

1. `_afficher_application` montre le bouton Parler et lance le fil session **après** l'UI (`UI_PRETE` puis `session.start()`).
2. Le fil ouvre d'abord sounddevice / micro / sortie, **puis** `connect(ws://127.0.0.1:8001/hostagent)` et la poignée hello/ready. `CANAL_PRET` n'arrive qu'après.
3. `enfoncer` armait `tenu`, passait la bulle en « écoute » et le bouton en « Parler… » **sans vérifier le canal**. `session.ws` est encore `None`.
4. `threading.Event` ne file pas les pulses : un appui-relâche pendant « Connexion… » est déjà `clear` quand `_boucle_tours` démarre. Capture jamais `start()`, zéro trame, EARS jamais appelé, aucun message « parole trop courte ». L'utilisateur répète une fois le canal prêt — et ça marche.

Les `GET /` → 404 avant `WebSocket /hostagent` sont les sondes santé (`http://127.0.0.1:8001/` toutes les 2 s, C2). Elles prouvent que l'UI tourne **avant** le WS ; elles ne perdent pas l'audio elles-mêmes.

**Hypothèse 2 — flux micro à démarrage paresseux (souffle du 8/09).** Écartée comme cause de ce bug. Le correctif « souffle » est le `start()` paresseux de la **sortie** (`talk._jouer`), pas du micro. `PushToTalkCapture` ouvre l'entrée à chaque `start()`. Un délai WASAPI au premier callback reste possible : tracé (`MIC_START` → `MIC_CHUNK attente_ms`) pour le prochain live, pas corrigé ici.

**Hypothèse 3 — premier segment trop court / EARS vide au warmup.** Non déclenchée si aucune trame ne part (cas 1). Tracée côté serveur (`AUDIO_RECV`, `TRANSCRIPT`) pour le prochain tour live.

## Traces (préfixe `C10 t=<monotonic>`)

| Événement | Où |
|---|---|
| `PTT_ON` / `PTT_OFF` / `PTT_IGNORE` | `native/presence/app.py` |
| `WS_OPEN` | Presence après poignée ; `talk.py` idem |
| `AUDIO_SEND n_trames n_samples` | Presence + `talk.py` |
| `MIC_START` / `MIC_CHUNK attente_ms` | `native/hostagent/windows_audio.py` |
| `AUDIO_RECV n_trames duree_s` / `TRANSCRIPT` | `dev/scripts/serve_hostagent.py` (`_enchainer` seulement) |

Live Presence non relancé ici (dégustation en cours + host-agent gelé). Au prochain lancement : un tour perdu doit montrer `PTT_IGNORE` ou un `PTT_ON` **avant** `WS_OPEN` ; un tour sain : `WS_OPEN` puis `PTT_ON` puis `AUDIO_SEND` puis côté serveur `AUDIO_RECV` / `TRANSCRIPT`.

## TDD

**Rouge** (code avant correctif, `enfoncer` arme l'écoute alors que `ws is None`) :

```
$ python -m pytest dev/tests/test_presence_premier_tour.py -q --tb=short
.FF
AssertionError: assert True is False   # application.enfonce
AttributeError: 'SessionVocale' object has no attribute 'canal_pret'
2 failed, 1 passed in 1.05s
```

Le test vert de mécanique (`test_un_appui_deja_relache_est_invisible_pour_la_boucle`) passait déjà : pulse PTT avant `_boucle_tours` → `capture.demarrages == 0`.

**Vert** :

```
$ python -m pytest dev/tests/test_presence_premier_tour.py --tb=short
============================= test session starts =============================
platform win32 -- Python 3.13.14, pytest-9.1.1
collected 2 items
dev\tests\test_presence_premier_tour.py ..                               [100%]
============================== 2 passed in 0.55s ==============================
```

Régression courte : `test_presence_interruption.py` + `test_windows_audio.py` — 10 passed.

## Correctif minimal

`SessionVocale.canal_pret` levé seulement après hello/ready, baissé à la déconnexion.

`enfoncer` : si le canal n'est pas prêt → statut « Canal pas encore prêt. », trace `PTT_IGNORE`, **pas** d'écoute feinte. L'appui après `CANAL_PRET` inchangé.

Pas de relance host-agent. MOUTH / `magpie_tts.py` non touchés.

## Diff résumé

- `native/presence/app.py` — `canal_pret`, gate PTT, traces C10
- `native/hostagent/windows_audio.py` — traces premier chunk micro
- `native/hostagent/talk.py` — traces WS_OPEN / AUDIO_SEND (chemin CLI)
- `dev/scripts/serve_hostagent.py` — traces AUDIO_RECV / TRANSCRIPT (réception EARS)
- `dev/tests/test_presence_premier_tour.py`

## Pour Thomas

Relancer **seulement Presence** (pas le host-agent tant que C9 n'a pas écrit « GPU »). Premier réflexe pendant « Connexion… » : la ligne d'état dit « Canal pas encore prêt. » au lieu d'un silence. Premier vrai tour après « Canal prêt. ».
