# hyper-ambient

hyper-ambient is a local, ambient voice presence. It listens, answers out loud, and keeps
real time on the machine: an ordinary turn comes back in 650 milliseconds without leaving
the computer.

What makes it different fits in one sentence: **it is not an assistant that contains
capabilities, it is a voice that plugs into the ones you already own.** When you ask for
development work, it does not invent it — it hands the work to the tools installed on your
machine, under your account and your sessions, then reports back by voice.

For heavy development work it is not the right tool, and it says so itself: it has no
visual interface for reading or editing a detailed result. It gives you the summary, then
invites you to open the tool in question.

French version: [README.md](README.md) · What data moves:
[DONNEES.en.md](DONNEES.en.md) ([Français](DONNEES.md))

## What it plugs into

| Tool | What it does with it |
|---|---|
| **Codex** | Hands over a task, collects the result, announces it out loud |
| **Claude Code** | Same |

Those two are the scope, and that is deliberate. If you name a tool that is not connected,
it says so rather than quietly picking another one: when you name a tool, you have a
reason — an open session, a context already loaded, a subscription.

## Architecture

- **Core in a container** — local models and the real-time reasoning service run in a
  Docker container.
- **Host agent** — connects the microphone and speakers to the core over a local channel.
  It is the only component that touches audio hardware.
- **Presence** — a small window showing state, transcripts, answers, and any remote call.

The local model handles short turns. A local classifier decides on every turn, and sends
to the remote model only what needs it: a complex request, or one that names a development
tool. What travels, and how to turn it off, is in [DONNEES.en.md](DONNEES.en.md).

## Requirements

- Windows 10 version 2004 or later, or Windows 11; PowerShell; a network connection for
  installation and, if you enable it, for the remote model.
- An NVIDIA GPU. The target budget is **8 GB of video memory**, and the whole stack must
  stay under 10 GB. Plan for at least 15 GB of system memory, about 40 GB free, and a
  CUDA-capable driver.
- Virtualisation enabled in the BIOS or UEFI. Docker Desktop, WSL2 and Python are
  installed or verified by the installer.
- A local clone of the repository. Keys for optional services stay with their owner; they
  never appear here.

## Installing on Windows

This is the supported platform today. From **any** PowerShell directory, replace the path
with your own clone and start with the diagnostic:

```powershell
& "C:\path\to\hyper-ambient\packaging\windows\installer.ps1" -Diagnostic
```

Then, to install or resume an interrupted installation:

```powershell
& "C:\path\to\hyper-ambient\packaging\windows\installer.ps1"
```

After that, the **hyper-ambient** desktop shortcut is enough. It calls this launcher,
which you can also run by hand:

```powershell
& "C:\path\to\hyper-ambient\packaging\windows\lancer.ps1"
```

The launcher checks what is already running, resumes the container without recreating it,
starts the model servers, the host agent and Presence, then prints the state of each part.
Run it twice and it will not open a second window.

What the installer does in detail, including what it cannot automate — Docker Desktop
requires a human to accept its licence on first launch — is in
[the Windows guide](packaging/windows/README.md).

## macOS — shipped, not validated

The macOS port **is in this repository**: the audio abstraction, the interface
abstraction, and the packaging live in `packaging/macos/`. It has **never been run on a
real machine**, and we will not call it ready until a Mac has put it through its paces.

What the first macOS version will not have, and we know it in advance:

- **The Sofia voice will not exist.** It is a CUDA engine; a Mac forces a different
  engine, therefore a different timbre. That is the real breaking point, not the port
  itself.
- **Compute runs without CUDA**: Metal for the language model, most likely a different
  transcription engine, synthesis on the CPU. Latencies remain to be measured on site.
- **The application is not notarised**: the first launch will ask for explicit approval.

### The validation process

The port will only be published as supported after this path:

1. Preparation happens on Windows: dependencies, packaging, launcher, declared
   permissions. Everything verifiable without a Mac is verified first.
2. Someone with a Mac runs a written protocol — about thirty minutes, each step saying
   what to do and what you should see or hear.
3. The verdict reads in a minute: **no blocking defect and the voice judged acceptable,
   we publish; a single blocking defect, or a voice judged robotic, we do not.**
4. Until that verdict exists, macOS stays announced as not validated, here and in the
   documentation.

If you have a Mac and want to help, this is exactly where it happens.

## Updates are reviewed once a week

This repository is watched by an automated **weekly round**. Once a week it collects what
you leave here — issues, comments, pull requests — sorts what can be acted on, and
prepares the work.

What it never does is decide for us. It prepares branches and **draft** pull requests; no
merge is automatic, and every change is tried by hand before it ships. The agents that
prepare that work run in a clone with no remote: they are structurally unable to push.

In practice, if you open an issue, expect **up to a week** before it is picked up. That is
not inattention, it is the chosen rhythm.

The workflow lives in `automation/n8n/`, with its settings in plain sight: the schedule,
the number of topics per run and the age window are changed in the interface, without
touching code.

## What comes next

- **macOS**: see above. The core deliberately stays on the NVIDIA GPU.
- **Spanish**: announced, then postponed. French and English ship today.
- **Guided setup**: onboarding assisted by the local model is specified, but replaced for
  now by plain menus.
- **Interface**: optional video, notification area, a global shortcut, and some
  accessibility checks in real use remain to be shipped or verified.
- **Continuity**: long voice memory, recovery after a server restart, and a suitable
  health probe are still open.

These limits are deliberate and tracked. None of them stands in for a step the installer
could already automate.
