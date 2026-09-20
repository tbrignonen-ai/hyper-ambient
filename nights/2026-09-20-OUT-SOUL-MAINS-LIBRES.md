---
date: 2026-09-20
heure: ~16:52 Europe/Paris
type: out
lane: SOUL-MAINS-LIBRES
complexity: complex
notify: OG
cible: OG (puis OG → OC)
auteur: Cursor (Grok 4.6)
related: ["[[2026-09-20-BRIEF-CURSOR-SOUL-MAINS-LIBRES]]"]
nudge: unique — pytest + relance host-agent, Presence non lancée, Codex non appelé
---

# OUT — SOUL (longueur + stop) + fix Mains libres mort

**STOP opérateur :** Presence non lancée. Pas de pythonw / Start-Process / hyper-ambient.bat / 2e instance. Codex non appelé.

**Thomas recharge Presence UNE fois.**

## A — SOUL

Cause : le prompt disait « une ou quelques phrases » et « développe si le sujet l'exige ». Few-shot MOUTH enseignait les relances (« Et toi, ta soirée ? ») et les longs développements.

Règles durcies FR + EN dans `src/brain/local_prompt.py` (via `i18n.system_prompt`) et alignées dans `src/mouth/normalize.py` `VOICE_SYSTEM_PROMPT` :

1. Salutation / oui-non / fait simple = **une phrase max**. Explication = 2–4 phrases. Détail seulement si demandé (« explique », « développe », « pourquoi »).
2. Interdit en fin de tour : « je peux aussi », « sinon je peux », « veux-tu que », suites, alternatives. Quand c'est dit, **stop**.
3. Pas de liste, Markdown, meta (« en tant qu'IA »).
4. Identité Hyper Ambient + accord féminin FR conservés.

Host-agent relancé (pid 1135) pour charger le prompt. Presence non touchée côté process.

## B — Mains libres mort en live

Cause retenue : trois défauts empilaient le symptôme « logs = PTT hold + stop, jamais `écoute toggle` ».

1. **Flag souvent OFF** (défaut `mains_libres: false`) et feedback trop faible après un hold-release unique en ON.
2. **Focus** : après clic sur le bouton Mains libres, `_focus_autorise_ptt` bloquait Ctrl+Espace / Espace (focus sur un autre `Button`).
3. **Latch `_touche_parler_enfoncee`** : auto-repeat clavier avalait aussi un clic souris ; Ctrl+Espace sans `KeyRelease` Control laissait le latch coincé. Le 2e appui ne partait pas.

Correctifs (`native/presence/app.py`, `onboarding.py`, i18n) :

- Sync `configuration.mains_libres` ↔ `session.mains_libres` à chaque bascule + log `mains_libres=ON/OFF sync`.
- Raccourci **actif hors Speak** dès que ON (sauf champ texte). Focus rendu à Parler après bascule.
- Ctrl+Espace : bind extra `<KeyRelease-space>` pour déverrouiller si Ctrl est relâché avant Space.
- Latch clavier seulement : un clic souris n'est plus ignoré si la touche est coincée.
- UI ON : bouton **Écoute…** pendant l'appui, **Appuie pour envoyer** après relâche ; statut « Écoute… Réappuie pour envoyer. » — plus de silence après un hold-release unique.
- Logs : `mains_libres=ON start` / `mains_libres=ON send`.

PTT hold inchangé si OFF. JeV toujours seulement si ON.

## Preuve (exécutée)

```
$ python -m py_compile native/presence/app.py native/presence/onboarding.py \
    src/i18n/__init__.py src/brain/local_prompt.py src/mouth/normalize.py

$ python -m pytest -q dev/tests/test_c8_i18n.py \
    dev/tests/test_presence_stop_mains_libres.py \
    dev/tests/test_presence_mains_libres.py \
    dev/tests/test_presence_onboarding.py \
    dev/tests/test_presence_interruption.py
64 passed in 2.61s

$ docker exec mother-core-dev bash -lc '/workspace/dev/scripts/relance_hostagent.sh'
carte figee: brain=llamacpp model=granite-4.2-3b-Q4_K_M.gguf ears=faster-whisper/large-v3 mouth=magpie/Sofia/cuda
langue: fr
config outils: searxng=oui tavily=non codex=oui claude=oui muse=non
TERM host-agent: 807
host-agent relance, pid 1135
host-agent pret, pid 1135

LANG  : fr (prompt/nombres ; carte ASR/TTS=fr/fr)
OUTILS: ask_claude, ask_codex, calculer, web_search — porte en mode auto
écoute sur 0.0.0.0:8001 /hostagent
```

## Retest manuel (Thomas, après recharge Presence)

1. Bouton **Mains libres : ON**. Le statut dit d'appuyer Parler / raccourci, réappuyer pour envoyer.
2. Un appui → bouton **Écoute…**. Relâcher → **Appuie pour envoyer**, statut visible. Deuxième appui → **Envoi…**.
3. Logs Presence : `mains_libres=ON start` puis `mains_libres=ON send` (plus seulement `bouton : enfoncé`).
4. Ctrl+Espace : même toggle, même si le focus n'est pas sur Parler.
5. Salutation vocale = une phrase, sans « je peux aussi / sinon / veux-tu que ».

EXIT=0. Lane close.

NOTIFY=OG
ACTION: SendToAgent OG — lane SOUL-MAINS-LIBRES done
