@echo off
REM Lanceur d'hyper-ambient. Double-clic : rien a taper, aucun terminal a
REM garder ouvert. Le serveur doit tourner dans mother-core-dev.
cd /d "%~dp0..\.."
start "" pythonw native\presence\app.py
