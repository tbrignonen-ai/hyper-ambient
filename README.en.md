# hyper-ambient

hyper-ambient is a local ambient voice for Windows. It listens and answers aloud while
keeping real-time work on the computer. For complex turns — and always when a harness is
named — it uses a remote model to reason and drive already installed development
harnesses: Codex, Claude Code, and Cursor.

It is a companion for work at the computer, not a replacement for a development
environment. It can hand simple tasks to those harnesses and speak a summary. For
intensive development, use Codex, Claude Code, or Cursor directly: hyper-ambient has no
visual interface for reading, editing, or validating their detailed results.

French version: [README.md](README.md). Data flows: [DONNEES.en.md](DONNEES.en.md)
([French](DONNEES.md)).

## Architecture

- **Docker core** — local models and the real-time reasoning service run in the
  `mother-core-dev` container.
- **Windows host agent** — connects microphone, speakers, and the core over a local
  channel.
- **Tkinter Presence** — the Windows window shows status, transcripts, replies, and when
  a remote call is in progress.

The local model handles short turns. The remote model receives a turn only when a
complex turn requires it or when the user names a harness; it then orchestrates the
available tools. [DONNEES.en.md](DONNEES.en.md) describes those flows and how to disable
them.

## Requirements

- Windows 10 version 2004 or later, or Windows 11; PowerShell; network access to
  download dependencies and, when configured, use the remote model.
- NVIDIA GPU: the intended budget is **8 GB VRAM**, and all stages together must stay
  within **10 GB**. Allow at least 15 GB of system RAM, about 40 GB free storage, and a
  CUDA-compatible NVIDIA driver.
- BIOS/UEFI virtualization enabled. The installer installs or checks Docker Desktop,
  WSL2, and Python.
- A local clone of this repository. Optional service credentials must be supplied by
  their owner and are never included in this repository.

## Install on Windows

The installer is the documented installation path. From **any** PowerShell directory,
replace the path below with your clone path and run the diagnostic first:

```powershell
& "C:\path\to\hyper-ambient\packaging\windows\installer.ps1" -Diagnostic
```

To install or resume the installation:

```powershell
& "C:\path\to\hyper-ambient\packaging\windows\installer.ps1"
```

The [Windows guide](packaging/windows/README.md) explains its checks, Docker Desktop,
the launcher, and the genuinely manual limits. Do not run the script without
`-Diagnostic` on a machine you are diagnosing.

After installation, use the **hyper-ambient** shortcut or, from any PowerShell
directory:

```powershell
& "C:\path\to\hyper-ambient\packaging\windows\lancer.ps1"
```

The launcher checks existing services, resumes the container without recreating it, and
opens Presence.

## What is next

- **macOS**: the terminal is written but has never run on a real Mac, so it is not yet
  supported. The core intentionally remains on the Windows PC’s NVIDIA GPU.
- **Spanish**: announced, then deferred; French and English are the currently delivered
  languages.
- **Onboarding**: local-model-assisted onboarding is specified, but is currently
  replaced by standard Tkinter menus. Guided declaration and verification of remote
  services and harnesses are still missing.
- **Interface**: optional video, a notification-area icon, a global Windows shortcut,
  and real-path accessibility checks remain to be delivered or verified.
- **Continuity**: longer voice memory, recovery after a server restart, complete-turn
  mandate notifications, and a suitable health probe are still open work.

These limits are tracked deliberately; they are not substitutes for an installation step
the installer can already automate.
