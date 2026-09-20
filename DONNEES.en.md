# Data leaving the machine

Code reviewed: `src/brain/`, `src/ears/`, `src/mouth/`, `src/hostagent/`,
`native/`, and `dev/scripts/serve_hostagent.py`.

## Items to correct before publication

- A transcription and recent text history are sent to the remote model when it
  is enabled. They do not always stay on the machine.
- JeV receives the transcription when it is enabled.
- Web search can call DuckDuckGo without a key after a SearXNG failure.
- An optional Muse bridge exists in addition to Codex and Claude. A Qwen Code
  bridge also exists in `native/`, but is not connected to the current
  host-agent.
- The feedback link opens GitHub in the browser after an explicit user action.

| Data sent | Destination | When | How to disable |
|---|---|---|---|
| Transcription, system instruction, recent history, and possible tool results; API key in the authentication header when configured | Model endpoint configured by the user | `stepfun`, `openai`/compatible, or router mode with a remote path. Fallback can call the remote model before returning to local. | Use `BRAIN_SERVICE=llamacpp` with a local URL; do not configure a remote endpoint or key. |
| Transcription; API key in the authentication header | JeV API (`api.typesafe.ai`) | Hands-free mode is on and a JeV key is present. Warm-up requests without a transcription can also keep the connection alive. | Remove the JeV key or turn off hands-free mode. |
| Search query; provider key in the header where required | Configured SearXNG, then DuckDuckGo, Tavily, Brave, Exa, Jina, or Serper | The search tool is registered when a SearXNG URL or at least one search key is configured. DuckDuckGo is the keyless fallback. | Remove `SEARXNG_URL` and every search key; the tool is then not registered. |
| Voice question converted to text | Local Codex or Claude bridge, then the user-installed and user-connected CLI services | A bridge token is configured and the model selects the tool. | Remove the relevant bridge token or do not run its bridge. |
| Voice question converted to text | Configured Muse bridge URL | `MUSE_BRIDGE_URL` is set and the model selects `ask_muse`. | Remove `MUSE_BRIDGE_URL`. |
| Voice question converted to text | Qwen Code through the Qwen bridge | `native/qwenbridge` is started separately and receives a request. The current host-agent does not register it as a tool. | Do not run that bridge. |
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
- `RemoteTTS` contains a remote API client, but the current host-agent does not
  instantiate it from any `MOUTH_BACKEND` choice. Magpie uses `127.0.0.1`.

This describes explicit calls in the reviewed code. User-installed CLIs and
model libraries have their own network behaviour outside this code.
