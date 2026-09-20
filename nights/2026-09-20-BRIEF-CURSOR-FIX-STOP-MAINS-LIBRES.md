# BRIEF Cursor — FIX Stop + Mains libres réel — 20 sept 15:40
Complexité: complex → NOTIFY OG
URGENCE BGB demain.

## INTERDITS ABSOLUS
- NE PAS lancer Presence / pythonw / Start-Process app.py / hyper-ambient.bat
- NE PAS ouvrir 2e instance. Thomas a déjà Presence ouverte — il recharge lui-même (fermer/rouvrir ou tu dis « recharge l'UI » dans OUT).
- Si tu dois tester: py_compile + pytest seulement.

## Bugs Thomas (retest live)
1. **Pas de bouton Stop** — pendant que Magpie parle, impossible de couper (sauf peut-être ré-appuyer Parler, pas visible).
2. **Mains libres ne fonctionne pas** — il attend parler SANS maintenir Parler. Livré = seulement filtre JeV + PTT obligatoire. Inutilisable pour le jury « mains libres ».

## Patch demandé

### A — Bouton Stop
- Bouton visible « Stop » (i18n FR/EN) à côté de Parler.
- Action: interrompre lecture TTS en cours (réutiliser interrompre / sortie.abort déjà dans consommer_reponse) + statut « Interrompue ».
- Clavier: Escape peut rester quitter OU Stop pendant parole — préférer Stop si en train de parler, sinon masquer/comportement actuel. Documente le choix.
- takefocus + focus visible.

### B — Mains libres = écoute sans maintenir
Quand mains_libres=True:
- Un appui sur Parler (ou raccourci) **démarre** l'écoute (toggle ON), un second appui **OU** silence VAD (~0.8–1.2 s) **envoie** le tour (toggle OFF).
- Pas besoin de maintenir enfoncé.
- Afficher clairement l'état: « Écoute… / Envoi… ».
- JeV filtre reste actif seulement si mains_libres (déjà).
- Si VAD trop gros pour 45 min: minimum viable = toggle press-to-start / press-to-send (sans hold). VAD = bonus.

### C — OUT
- `C:\Users\thoma\obsidian-vault\10-Projects\MOTHER\nights\2026-09-20-OUT-FIX-STOP-MAINS-LIBRES.md`
- `C:\Users\thoma\obsidian-vault\10-Projects\MOTHER\nights\2026-09-20-EXIT-FIX-STOP-MAINS-LIBRES.txt` (0=OK)
Miroir `D:\BGB Training\MOTHER-dev\nights\`
Dans OUT: « Thomas: ferme Presence et relance UNE fois via hyper-ambient.bat » — TOI tu ne lances pas.