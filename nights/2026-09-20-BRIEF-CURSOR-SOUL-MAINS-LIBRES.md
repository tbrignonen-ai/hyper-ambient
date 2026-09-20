# BRIEF Cursor — SOUL + fix Mains libres mort — 20 sept 16:45
Complexité: complex → NOTIFY OG. URGENCE BGB demain.
INTERDIT: lancer Presence / multi-instances / Codex. Thomas a Presence ouverte.

## A — SOUL (system prompt)
Fichiers: `src/brain/local_prompt.py` (source via `i18n.system_prompt`), et aligner `src/mouth/normalize.py` VOICE_SYSTEM_PROMPT si encore injecté quelque part.

Thomas: elle parle trop; ne distingue pas réponse courte vs longue; finit souvent par « je peux aussi / sinon je peux… ».

Règles à durcir (FR + EN):
1. Calibrer la longueur: salutation / oui-non / fait simple = **1 phrase max**. Explication = 2–4 phrases. Détail seulement si demandé (« explique », « développe », « pourquoi »).
2. **Interdit** de proposer des capacités complémentaires, suites, alternatives, ou « je peux aussi… / sinon… / veux-tu que… » en fin de tour. Quand c'est dit, **stop**.
3. Pas de listes, markdown, meta (« en tant qu'IA »).
4. Garder identité Hyper Ambient + accord féminin FR.

Relancer host-agent après patch prompt (`relance_hostagent.sh`) — OK. Pas de Presence.

## B — Mains libres mort en live
Config actuelle souvent `mains_libres: false`. Code toggle existe (`action_appui_parler`, `_demarrer_ecoute_toggle` / `_envoyer_ecoute_toggle`).

Logs Thomas: pas de `bouton : écoute toggle` — seulement PTT hold + `stop : coupure voix`. Donc soit le flag UI n'est pas ON au moment du test, soit le 2e appui ne part pas, soit le session thread n'arme pas.

À diagnostiquer et corriger:
1. Sync `configuration.mains_libres` ↔ `session.mains_libres` à chaque bascule (déjà partiel) — vérifier race.
2. Si `_touche_parler_enfoncee` ou focus bloque le 2e appui: fix.
3. Raccourci `ctrl-space`: s'assurer toggle marche (pas seulement hold).
4. Feedback UI ultra clair quand ON: bouton Parler affiche « Écoute… » / « Appuie pour envoyer », statut visible; si ON mais user fait un hold-release unique sans 2e appui, ne pas rester muet sans statut.
5. Journaliser clairement `mains_libres=ON start/send`.
6. Tests pytest + re-preuve.

## OUT
- `C:\Users\thoma\obsidian-vault\10-Projects\MOTHER\nights\2026-09-20-OUT-SOUL-MAINS-LIBRES.md`
- `C:\Users\thoma\obsidian-vault\10-Projects\MOTHER\nights\2026-09-20-EXIT-SOUL-MAINS-LIBRES.txt`
Miroir repo nights/. Dans OUT: « Thomas recharge Presence UNE fois ».