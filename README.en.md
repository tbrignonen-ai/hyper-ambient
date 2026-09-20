# Hyper Ambient 0.1 — English

Hyper Ambient is a local voice on Windows: it listens, thinks, and answers out loud.
French is the default language of the product and of the viva. English 0.1 is the same
build, switched with `HA_LANG=en` (or `HYPER_AMBIENT_LANG=en`), or from the Presence
language radios (saved in `%LOCALAPPDATA%/hyper-ambient/presence.json`).

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

Anything other than `en` / `en-US` falls back to French. Do not recreate Docker to change this: set the variable in `.env.local`, the host-agent launch script, or the in-app language control. `HA_LANG` in the environment still wins over the saved file.

## Accessibility (low vision + keyboard; not a deaf-user mode)

- Tab / Enter: every control takes focus; the Talk button can be held with Enter.
- Transcripts, replies and remote-call status stay on screen as text.
- Optional **High contrast** (WCAG 1.4.11, graphical objects ≥ 3:1 against the dark field).
- Hands-free: with a TypeSafe JeV key, Hyper Ambient only answers when addressed; without a key, hold Talk. This is not a mode for deaf users.

## Feedback

Presence has a **Send feedback** button. It opens a GitHub issue:
https://github.com/tbrignonen-ai/hyper-ambient/issues/new
No secret is sent. Reading the queue daily is an ops habit, not an in-app cron.

## Run

Windows app: `native/presence/hyper-ambient.bat` (pythonw, no console). Stdout/stderr are reattached to `%LOCALAPPDATA%/hyper-ambient/presence.log` so PortAudio still has valid C fds (C13). Fallback: `python -u native/presence/app.py`.
The voice stack lives in the `mother-core-dev` container (`:8001` host-agent).

Developer README (container, make targets): see `README.md`.
