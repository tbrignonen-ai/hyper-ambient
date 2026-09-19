---
date: 2026-09-19
type: passation
de: Claude (lead technique + interlocuteur tests live de Thomas)
pour: Grok bot (organisateur — coordonne ses bots, Cursor, Codex, Step-5)
related: ["[[2026-09-19-CLAUDE-POINT-SESSION]]"]
---

# Claude → Grok bot : ma part, et ce qui est à orchestrer

## Répartition (Thomas, 19/09)
- **Grok bot** : organisateur. Ordre des lanes, dispatch Cursor / Codex / Step-5 / bots, horloge, kanban.
- **Claude** : lead technique (décisions techniques, briefs, vérification des livrables) + interlocuteur de Thomas pour les tests live et ajustements.
- **Thomas** : juge à l'oreille et à l'œil, tranche les choix produit.

## Ce que je garde (en cours avec Thomas)
**Étape 1 — figer les modèles locaux** par dégustation à l'aveugle : voix (échantillons prêts), oreille, cerveau ;
contraintes : 10 Go VRAM au total, français, Windows natif. Sortie : `nights/2026-09-19-CARTE-FIGEE.md`.
Veille HF (Cursor) en appui. Je préviens Grok bot quand la carte est figée.

## Lanes à orchestrer par Grok bot (briefs techniques : je les écris ou je les relis)
| Lane | Contenu | Brief | Dépend de |
|---|---|---|---|
| **C1** | Host-agent charge enfin `.env.local` (voix, cerveau, outils) — cause racine d'abord | `2026-09-19-BRIEF-CURSOR.md` | — (P0) |
| **C2** | Alerte + reprise visibles (démo jury obligatoire) | `2026-09-19-BRIEF-CURSOR.md` | — |
| **C3** | JeV en entrée : 12 critères en 1 appel, connexion gardée, seuils, repli bouton | à écrire | C1 |
| **C4** | Web multi-fournisseurs en chaîne de repli + clés facultatives | à écrire | C1 |
| **C5** | Option TTS distante (StepAudio d'abord) | à écrire | C1, carte figée |
| **C6** | Onboarding vocal + visuel (VRAM/modèles temps réel, assemblage) | à écrire | carte figée |
| **C7** | App native Windows : inventaire dépendances Docker → prototype installateur | à écrire | carte figée |
| **V1** | Veille HF nocturne : cron qui lance `dev/scripts/veille_hf.py` → note du jour | script livré | — |
| **X1** | Annexe dossier BGB 15–30 p. | `2026-09-19-BRIEF-CODEX.md` | — |

Deadline dossier + soutenance : lundi. Démos obligatoires jury : **alerte + reprise** (C2) et **service tiers** (C1 ; JeV C3 en bonus visible).

## Règles techniques communes à toutes les lanes
Fichiers disjoints par lane · TDD (rouge vu puis vert) · cause racine avant correctif · aucune valeur de secret affichée ·
pas de docker recreate · pas de commit sans accord Thomas · « fait » = commande + sortie collée dans l'OUT.
Escalade vers un harnais = **toujours décidée par l'utilisateur**, jamais par un modèle.

## Précisions Thomas (~14:45) pour C5 / C6
- C5 : TTS distant = **n'importe quel fournisseur** ; après test de la clé, lister ses voix et laisser choisir (catalogue récupéré par API, pas codé en dur).
- C6 : étape « voix distante » **en fin d'onboarding** ; questions simples → modèle local, questions complexes → modèle distant en priorité, local en repli.

- Après CARTE-FIGEE : copier **uniquement** les modèles retenus vers le SSD `E:` (lane à assigner, vérifier l intégrité par SHA256 après copie).

- **C8 — Version EN 0.1** (après carte figée) : i18n des chaînes UI/onboarding, annonces vocales (`ANNONCES_OUTILS`), prompts système, normalisation de texte (`src/mouth/normalize.py` est FR), critères JeV, README EN. FR reste le défaut.

## Défauts relevés en dégustation cerveaux (à répartir)
Nombres mal prononcés (normalisation FR) · bouton STOP dédié · recherche web KO en live · identité « Hyper Ambient » dans le prompt · réponses trop longues · Presence tombée 2 fois. Détail : [[2026-09-19-DEGUSTATION-CERVEAUX-RESULTATS]].
