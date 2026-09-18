---
date: 2026-09-15
type: wrap
auteur: Claude (lead technique)
related:
  - "[[2026-09-13-CLAUDE-REPRISE]]"
  - "[[2026-09-15-ASSIGN-CURSOR-DESIGN]]"
---

# Wrap séance test — 15 septembre

## Préférences voix de Thomas (à respecter)

- Cible : **« comme Aurora Ray » — suave, féminine, agréable à écouter, qui parle plutôt lentement**.
- **Supertonic-3 `F5`, vitesse 0,88** : « c'est pas mal, retiens-la » → **défaut actuel**
  (`.env.local`, `relancer_routeur.sh`).
- **Supertonic-3 `F3`, vitesse 0,88** : dernière essayée, « avait l'air pas mal » → **finaliste**,
  à départager avec F5 à la prochaine séance.
- F1 (0,85) : essayée, pas retenue. Pocket estelle / Piper : « toujours les mêmes ».
- Il veut encore **d'autres voix FR** : Pocket et Supertonic sont épuisés (8 samples de plus dans
  `data/out/voix-nouvelles/`, dont Pocket fantine/eve/lola/anna/vera à accent anglophone probable).
  Prochaine piste = un moteur neuf (plus lourd, budget VRAM à mesurer).
- **L'interruption au bouton est indispensable** (« elle continue, c'est un problème »).

## Ce qui a changé (testé à l'oreille par Thomas)

| Sujet | Avant | Après | Preuve |
|---|---|---|---|
| Cerveau local | MiniCPM5-2B (swap du 13 pour le world, abandonné) — raisonnait en silence, recopiait les exemples du prompt (« Bonsoir. Ça va ? » à tout) | **Luciole-8B** remis (modèle d'avant le 13), `enable_thinking:false` sur le canal local | Canberra en test direct ; `test_reflex_sans_raisonnement.py` |
| Voix | Pocket estelle + gain **+9 dB** (crêtes 6 dB au-dessus du plafond → saturation) | **Supertonic F5 0,88**, gain **+3 dB** | `test_supertonic_tts.py` (3) ; recette de bout en bout OK |
| Interruption | le bouton ne coupait pas la réponse | appui pendant la réponse → voix coupée (tampon jeté), micro ouvert, socket vidée | `test_presence_interruption.py` (2), 15 verts |
| Routeur | — | option `BRAIN_REFLEX_ANSWERS` (0 = tout au distant) ; **laissée à 1** : Thomas veut que le local réponde la plupart du temps | `test_router_sans_reponse_reflexe.py` |
| Design fenêtre | — | modifié par Cursor/Muse selon la demande de Thomas (« c'est cool ») | [[2026-09-15-ASSIGN-CURSOR-DESIGN]] |

VRAM avec Luciole-8B : **8,4 Go** (sous le plafond 10 Go). Luciole met **~5 min 30** à charger
(lecture du GGUF depuis D: à travers Docker) — prévoir ce délai à chaque démarrage.

## Ouvert — prochaine séance, dans l'ordre

1. **L'appel au modèle distant ne part plus** (Thomas). Constat log : deep HTTP 200 au démarrage,
   mais **tous les tours routés `reflex`** depuis Luciole. Hypothèse à vérifier : le classifieur
   (`/completion` + GBNF, `router.py`) tourne sur Luciole et ne dit jamais ESCALADE. Mesurer sur
   5 questions dures avant de toucher quoi que ce soit.
2. **Départager F5 / F3**, puis figer.
3. **Annulation côté serveur** : aujourd'hui la réponse coupée continue d'être générée ; la question
   suivante part après la fin.
4. **Reconnexion de la fenêtre** : après une relance du host-agent, elle ne voit la coupure qu'au
   premier appui, et cette phrase est perdue.
5. Latence premier son Supertonic ~3 s (synthèse par phrase entière).
6. Nouvelles voix FR hors Pocket/Supertonic.

## Git

**Commité et poussé le 15 sept au soir** sur `nuit/2026-08-27` (`3f4f092`..`8cac524`, 6 commits par thème + les 4 du 6 sept). Suite de tests : 1001 verts, 2 échecs tkinter dans le conteneur (verts sur l’hôte). Fichiers du jour : `src/mouth/supertonic_tts.py`,
`src/brain/openai_compat.py`, `src/brain/router.py`, `native/presence/app.py`,
`dev/scripts/serve_hostagent.py`, `dev/scripts/relancer_routeur.sh`, 4 tests neufs (`.env.local` modifié localement, ignoré par git).
