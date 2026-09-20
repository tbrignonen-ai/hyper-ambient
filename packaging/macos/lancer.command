#!/bin/sh
# Lanceur macOS d'hyper-ambient — équivalent de native/presence/hyper-ambient.bat.
#
# Phase 1 (dev interne) : un .command est double-cliquable dans le Finder et
# ouvre une fenêtre Terminal. Acceptable en dev ; la distribution passera par
# un bundle .app (packaging/macos/Info.plist, étude portage §4.2).
#
# Première utilisation :  chmod +x packaging/macos/lancer.command
# Le serveur (le cœur) doit tourner dans mother-core-dev, comme sur Windows.

set -eu

RACINE="$(cd "$(dirname "$0")/../.." && pwd)"

# app.py insère lui-même la racine et native/presence dans sys.path. On les
# pose aussi ici pour que les scripts de recette lancés depuis ce shell
# trouvent `src.*` et `native.*`.
PYTHONPATH="$RACINE:$RACINE/src${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONPATH

cd "$RACINE"

# Pas d'équivalent à pythonw : un .command ouvre de toute façon un Terminal.
# Si les descripteurs 1/2 étaient fermés, app.py les rattache à
# ~/.hyper-ambient/presence.log (assurer_stdio) — la sortie reste consultable.
# HYPERAMBIENT_PYTHON permet de viser un interpréteur précis (Homebrew,
# pyenv, venv) : le python3 système n'a pas toujours tkinter 8.6 ni
# sounddevice, et c'est lui qui recevra la permission micro TCC.
INTERPRETEUR="${HYPERAMBIENT_PYTHON:-python3}"

exec "$INTERPRETEUR" -u "$RACINE/native/presence/app.py" "$@"
