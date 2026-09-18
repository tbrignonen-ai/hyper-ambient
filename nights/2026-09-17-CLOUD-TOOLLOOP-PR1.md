---
date: 2026-09-17
heure: ~21:42 Europe/Paris
type: out-cloud
auteur: OC
---

# Cloud agent DONE — tool-loop + Presence

- PR: https://github.com/tbrignonen-ai/hyper-ambient/pull/1
- Branch: `cursor/tool-loop-reflex-c303`
- +686/-46 · 14 files · **519 tests** verts
- REFLEXE sans `tools=` ; 1 tool call / turn ; args tronqués 800
- Escalade: `ask_codex` 1× OK
- Codex bridge / Hermes / SAWB / docker: non touchés
- Next hôte: merge ou pull branche → re-smoke PTT « Bonjour » + `:8765`