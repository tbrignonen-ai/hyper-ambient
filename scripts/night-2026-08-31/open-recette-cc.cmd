@echo off
title Claude recette MOTHER
cd /d "D:\BGB Training\MOTHER-dev"
echo.
echo === BRIEF charge : ASSIGN-RECETTE-CC.md ===
echo.
"C:\Users\thoma\.local\bin\claude.exe" --add-dir "C:\Users\thoma\obsidian-vault\10-Projects\MOTHER" --append-system-prompt-file "C:\Users\thoma\obsidian-vault\10-Projects\MOTHER\nights\2026-08-31-ASSIGN-RECETTE-CC.md" "Execute maintenant l'assignation recette dans nights/2026-08-31-ASSIGN-RECETTE-CC.md. Thomas est devant toi. Verifie Operate night_health_vault_note, montre-lui ce qu'il doit voir, prends son feedback, ecris nights/2026-08-31-FEEDBACK.md. Ne merge pas. Ne touche pas hermes."
pause
