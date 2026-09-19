# Hyper Ambient 0.1 — English

Hyper Ambient is a local voice on Windows: it listens, thinks, and answers out loud.
French is the default language of the product and of the viva. English 0.1 is the same
build, switched with `HA_LANG=en` (or `HYPER_AMBIENT_LANG=en`).

## Frozen local models (19 Sep 2026)

| Piece | Model |
|---|---|
| Brain | IBM Granite 4.2 3B Q4_K_M (llama-server, CUDA) |
| Ear | Whisper large-v3 int8 (faster-whisper, CUDA) |
| Voice | Magpie multilingual 357M, speaker Sofia (CUDA) |

Optional keys (all empty = the app still runs): TypeSafe JeV, web search providers, remote TTS, remote text model.

## Switch language

```
HA_LANG=en
```

This selects:

- Presence / onboarding copy
- Spoken tool announcements (`I'll ask Codex…`)
- Local system prompt (“You are Hyper Ambient…”)
- Number normalisation for TTS (`3:30` → `three thirty`)
- JeV criterion labels sent to TypeSafe

Anything other than `en` / `en-US` falls back to French. Do not recreate Docker to change this: set the variable in `.env.local` or the host-agent launch script.

## Run

Windows app: `native/presence/hyper-ambient.bat` (or `python -u native/presence/app.py`).
The voice stack lives in the `mother-core-dev` container (`:8001` host-agent).

Developer README (container, make targets): see `README.md`.
