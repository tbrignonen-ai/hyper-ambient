---
date: 2026-09-20
heure: ~11:05 Europe/Paris
type: out
lane: TAQUET-ANNEXE
auteur: Claude (lead technique)
cible: OG puis OC
related: ["[[2026-09-19-ANNEXE-TECH-HYPER-AMBIANT]]", "[[2026-09-19-CARTE-FIGEE]]", "[[2026-09-20-MAKINGOF-ACCOUNTABILITY]]"]
---

# OUT — TAQUET ANNEXE (1 h)

Fichier travaillé : `nights/2026-09-19-ANNEXE-TECH-HYPER-AMBIANT.md` (374 lignes). Aucun autre fichier modifié, aucun code touché, aucun commit.

## Changelog

| # | Changement | Preuve utilisée |
|---|---|---|
| 1 | **Carte figée intégrée** : la table des composants IA donne Granite 4.2 3B Q4_K_M, Whisper large-v3 int8, Magpie TTS « Sofia », avec latences mesurées et 7,3 Go de mémoire graphique. Replis documentés. Les 11 mentions « CARTE EN COURS » (dont les 8 des diagrammes) sont **toutes remplacées** : il n'en reste aucune. | `2026-09-19-CARTE-FIGEE.md`, test live 19/09 |
| 2 | **Section anglais 0.1** ajoutée au résumé exécutif : bascule `HA_LANG=en`, périmètre couvert, français par défaut. | `2026-09-19-C8-EN-OUT.md` (13 tests verts, FR inchangé) |
| 3 | **Making-of accountability** : le copier-coller brut (titre de niveau 1 en double, consigne « coller ici ») est réécrit en section **2.4 Outillage de flotte**, avec le tableau outil / registre / tableau de bord / démonstration et la règle de notification. | `account.py`, registre : 16 événements au 20/09 10h40 (11 ouvertures, 2 jalons, 3 clôtures), tableau horodaté 10:37 |
| 4 | **Démos C1/C2** : C2 passe de « à prouver » à **prouvé** (alerte + reprise, 7 tests verts, 3 captures) ; C1 précisé — chargement des clés prouvé (37 tests, registre de 0 à 5 outils), tour vocal complet vers un pont externe encore à faire. | `2026-09-19-C2-ALERTE.md`, `2026-09-19-C1-OUTILS.md` |
| 5 | **Accessibilité mesurée** : contrastes calculés sur les couleurs de l'interface — 12,9:1 (texte principal), 6,1:1 (texte secondaire), 14,3:1 (texte sur bouton clair), tous au-dessus du seuil AA, les deux premiers au niveau AAA. Focus clavier visible. Reste à prouver : lecteur d'écran et essai utilisateur. | Calcul WCAG sur `native/presence/app.py:51-56` |
| 6 | **Réseau et audio** : vérifié ce matin. L'audio entrant **n'est conservé nulle part** (aucune écriture de fichier audio hors bancs d'essai). En revanche le host-agent écoute `0.0.0.0` (`serve_hostagent.py:49`) — l'annexe le dit franchement et recommande de lier à `127.0.0.1` avant diffusion publique. | Lecture du code, 20/09 |
| 7 | **Retours utilisateurs** : requalifiés en hors périmètre 0.1 (aucun mécanisme automatisé), retour humain tracé dans les notes de séance. | Inventaire du dépôt |
| 8 | Trois sources ajoutées (S28 making-of, S29 anglais, S30 carte figée) et statut du document mis à jour. | — |

**Bilan des trous** : 24 → **20** `[À PROUVER]`, et ceux qui restent sont désormais soit des actions (lier à `127.0.0.1`, rendre la carte persistante), soit des preuves qui demandent la stack ou un tiers : Camunda de bout en bout, tour C1 vers un pont externe, onboarding live, lecteur d'écran, RGPD (base légale, rétention, droits du coffre), revue de publication.

## Un point de vigilance pour le dépôt public
L'écoute sur `0.0.0.0` est le seul sujet de sécurité réel trouvé ce matin. Il n'est pas exploitable tant que le port n'est pas publié et que le secret est exigé, mais c'est la première chose qu'un jury ou un lecteur du dépôt regardera. Correctif d'une ligne, à faire décider par Thomas (hors lane, je n'ai touché à aucun code).

## Reste à arbitrer avec Thomas
Pour les 20 trous restants : les prouver d'ici lundi, ou les présenter comme « cible » assumée. Mon avis : prouver Camunda et le tour C1 (ce sont les démonstrations attendues), assumer le reste en feuille de route.
