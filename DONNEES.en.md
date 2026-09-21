# Data leaving the machine

Code reviewed: `src/brain/`, `src/ears/`, `src/mouth/`, `src/hostagent/`,
`native/`, and `dev/scripts/serve_hostagent.py`.

| Data sent | Destination | When | How to disable |
|---|---|---|---|
| Transcription, system instruction, recent history, and possible tool results; API key in the authentication header when configured | Remote model endpoint configured by the user | Every difficult turn, and every turn that names a harness (Codex, Claude Code, or Cursor), uses the remote model so it can reason and drive the tools. | Use a local service and do not configure a remote endpoint or key; harnesses can no longer be driven through this path. |
| Transcription; API key in the authentication header | JeV API (`api.typesafe.ai`) | Hands-free mode is on and a JeV key is present. Warm-up requests without a transcription can also keep the connection alive. | Remove the JeV key or turn off hands-free mode. |
| Search query; provider key in the header where required | Configured SearXNG, then DuckDuckGo, Tavily, Brave, Exa, Jina, or Serper | The search tool is registered when a SearXNG URL or at least one search key is configured. DuckDuckGo is the keyless fallback. | Remove `SEARXNG_URL` and every search key; the tool is then not registered. |
| Question passed through a local Codex or Claude bridge | The user-installed, user-connected Codex or Claude CLI service | The bridge calls a connected CLI; that service's network behaviour depends on the user's account and CLI configuration. | Sign out of the CLI or do not run the bridge. |
| Opening an issue-creation page | GitHub through the system browser | Explicit click on the feedback link. The code adds no content to the URL. | Do not use the link. |

## What stays local in this scope

- The reviewed code does not send raw microphone audio to a remote service.
  Presence and the host-agent exchange audio frames over local `127.0.0.1`;
  the server rejects non-loopback peers.
- This scope contains no project telemetry call, account creation, or project
  server.
- Settings and keys come from the environment and local files. They are not
  sent to the project; a key is presented to the selected service for an
  authenticated request.
- Codex, Claude, Muse, and Qwen bridges are local. Their exchange with
  hyper-ambient does not make data leave the machine. Any remote service a
  connected CLI may call afterwards is described in the table.
- Conversation transcripts are written incrementally, one Markdown file per
  conversation, under
  `data/conversations/YYYY-MM-DD_HH-mm.md` at the installation root. The
  container writes there as `/workspace/data/conversations/`. They stay on the
  machine and trigger no network request. They contain the time, the speaker,
  the text, and tool or mandate lines so they can be read in a text editor.
  `%LOCALAPPDATA%\hyper-ambient\conversations\` applies only when the process
  runs outside the container.
- `RemoteTTS` contains a remote API client, but the current host-agent does not
  instantiate it from any `MOUTH_BACKEND` choice. Magpie uses `127.0.0.1`.

This describes explicit calls in the reviewed code. User-installed CLIs and
model libraries have their own network behaviour outside this code.

## Verified future work

An installed product will need to write transcripts to
`%LOCALAPPDATA%\hyper-ambient\conversations\`. With the current container
architecture, that requires an additional volume for this location; it does not
exist yet.
