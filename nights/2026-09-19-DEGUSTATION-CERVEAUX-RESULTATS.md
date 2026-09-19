---
date: 2026-09-19
type: resultats-test
protocole: "[[2026-09-19-PROTOCOLE-DEGUSTATION]]"
---

# Dégustation orale des cerveaux — résultats (aveugle levé après notation)

Méthode : 4 cerveaux présélectionnés à l'écrit (5 questions FR, sélection tolérante), chargés sous une lettre tirée au hasard ;
7 thèmes, **question improvisée par Thomas à la voix dans l'application réelle**, note 1–5 ; 33 captures d'écran (`degustation-19/cerveau/captures/`).
Voix pendant le test : Supertonic F5 (Magpie pas encore branchée) ; oreille : Whisper large-v3-turbo ; outils actifs (web, Claude, Codex).

| Lettre | Cerveau | Moyenne | Impression générale | Remarque |
|---|---|---|---|---|
| **Y** | **Ministral-3-8B-Instruct-2512 (Q4_K_M)** | **5,0 / 5** (7 notes) | 4 | **Retenu** |
| X | NeoHorse-1-9B (Q4_K_M) | 4,0 / 5 (7) | 4 | recherche web non aboutie ; bonne suite de conversation |
| W | Luciole-8B-Instruct-1.1 (Q4_K_M) | 2,7 / 5 (6) | 3 | **pénalisé par l'appli tombée** sur 2 thèmes (test à refaire pour être juste) |
| Z | NeoHorse-1-4B (Q4_K_M) | 2,0 / 5 (5) | 0 | incohérent sur consignes et info à jour |

## Défauts relevés hors cerveau (→ lanes)
1. **Les nombres sont mal prononcés** par la voix (Supertonic F5) → normalisation texte FR des nombres + vérifier avec Magpie Aria.
2. **Bouton STOP** explicite demandé (l'interruption par appui sur « parler » fonctionne, mais un stop dédié manque).
3. **Recherche web** : a échoué (X) ou n'a pas trouvé (W) → à diagnostiquer (SearXNG joignable depuis le host-agent ? résultat exploité ?).
4. **Identité** : le produit s'appelle **Hyper Ambient** — le prompt système doit le porter (un cerveau a répondu « ambiance »).
5. Réponses parfois trop longues après la réponse utile (→ critère JeV « longueur attendue »).
6. L'application Presence est tombée deux fois pendant le test (fenêtre fermée) → à investiguer.

## Granite 4.2 3B (test oral 17:41)
Moyenne **4,57/5** (7/7) — retenu. Commentaire Thomas : « s il prend moins de place que Ministral alors oui il est supérieur et ça laisse plus de place pour TTS ».

## Session 2 (17:41) — Granite 4.2 3B
Ministral jugé trop ancien (décembre 2025) → repli seulement. Candidat proposé par Thomas : `ibm-granite/granite-4.2-3b` (7 août 2026, Apache-2.0, FR testé officiellement, outils).
Présélection écrite OK (chargé en 15 s, 1er mot quasi immédiat). **Oral : 4,57 / 5** (7 notes : 5,5,4,4,5,5,4) — « s'il prend moins de place que Ministral, il est supérieur, et ça laisse plus de place pour le TTS ».
Empreinte : Q4_K_M 2,2 Go (≈ 3 Go en VRAM avec cache) contre ≈ 5,5 Go pour Ministral → **~2,5 Go libérés**.
**→ CERVEAU LOCAL RETENU : Granite 4.2 3B (Q4_K_M).** Repli : NeoHorse-1-9B puis Ministral-3-8B.
