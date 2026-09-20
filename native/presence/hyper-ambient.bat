@echo off
REM Lanceur d'hyper-ambient. Double-clic : rien a taper, aucun terminal a
REM garder ouvert. pythonw n'a pas de console : app.py rattache stdout/stderr
REM (et les fd C 1/2) a %LOCALAPPDATA%\hyper-ambient\presence.log (C13).
REM Repli diagnostic : python -u native\presence\app.py
REM Le serveur doit tourner dans mother-core-dev.
cd /d "%~dp0..\.."
start "" pythonw native\presence\app.py
