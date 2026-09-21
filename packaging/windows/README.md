# Installation Windows

The scripts locate the repository from their own location, so they can be called from
any PowerShell directory. Keep the script path in quotes: clone paths may contain
spaces.

## Start with a diagnostic

Replace `C:\path\to\hyper-ambient` with your clone path, then type exactly this in
PowerShell:

```powershell
& "C:\path\to\hyper-ambient\packaging\windows\installer.ps1" -Diagnostic
```

`-Diagnostic` changes nothing: it checks the Windows version, BIOS virtualization,
WSL2, Docker Desktop, NVIDIA GPU and driver, Python, free disk space, the
`mother-core-dev` container, and the shortcuts. A successful diagnostic ends with
`Verdict : pret`.

## Install or resume

Only after reviewing the diagnostic, run:

```powershell
& "C:\path\to\hyper-ambient\packaging\windows\installer.ps1"
```

The script is idempotent and resumes after the WSL2 reboot. It installs Python 3.13 for
the current user when possible, installs WSL2 without an Ubuntu distribution, installs
Docker Desktop with `winget`, starts Docker Desktop, builds the local image if needed,
starts `mother-core-dev`, creates an empty local configuration file when necessary, and
installs the shortcuts. It asks for administrator rights only for an action that needs
them and states why first. Nothing is installed into the host Python environment beyond
the Python runtime itself; application dependencies stay in Docker.

### Docker Desktop: what is and is not silent

The package download and installation are non-interactive as far as `winget` allows,
but a completely unattended Docker Desktop setup is not possible here. At Docker
Desktop’s first launch, its own window requires the user to accept its licence; the
script cannot and must not click through that consent. Instead, it launches Docker
Desktop, waits up to 180 seconds for its engine, and names the consent step if Docker
does not answer. Accept the licence in Docker Desktop, wait for the engine, then rerun
the same command.

## What still requires a person

- Enable virtualization in BIOS/UEFI: firmware settings are outside Windows.
- Restart Windows after `wsl --install`, then rerun the same command.
- Accept Docker Desktop’s first-run licence.
- Update an NVIDIA driver that is too old; the installer detects the issue but does not
  install a graphics driver.
- Provide credentials for optional services. The installer creates no credentials and
  never writes their values for you.

Model downloads and the first voice launch occur after machine bootstrap. The installer
reports this explicitly; it does not claim that bootstrap alone proves an end-to-end
voice conversation.

## Launch hyper-ambient

After a successful installation, start the product from its **hyper-ambient** Desktop
or Start-menu shortcut. Both shortcuts call `lancer.ps1`; they do not start a raw
command. From any PowerShell directory, the same launcher can be called directly:

```powershell
& "C:\path\to\hyper-ambient\packaging\windows\lancer.ps1"
```

The launcher does not install or recreate anything. It starts Docker Desktop when
needed, resumes the existing `mother-core-dev` container with `docker start`, checks
and starts the local BRAIN (port 8090), EARS (port 8091), and host-agent (port 8001),
then opens Presence. A second launch reports services already running. If a prerequisite
is absent, run `installer.ps1 -Diagnostic`; do not use the launcher as an installer.

## Shortcuts only

To install or remove shortcuts without administrator rights:

```powershell
& "C:\path\to\hyper-ambient\packaging\windows\installer_raccourcis.ps1"
& "C:\path\to\hyper-ambient\packaging\windows\installer_raccourcis.ps1" -Supprimer
```

Shortcuts do not install the product. They call `lancer.ps1`, which checks Docker
Desktop and the existing `mother-core-dev` container before it starts Presence.
