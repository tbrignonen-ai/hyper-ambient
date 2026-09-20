# BRIEF Cursor — poser JeV V2 (6 questions + regle de combinaison)
Lead : Claude (Opus). 2026-09-20 ~21h. PRIORITE 1.

## Source — lis-la en entier AVANT d'ecrire
`nights/2026-09-20-OUT-JEV-QUESTIONS-V2.md` (produit par Codex, valide par moi).
Elle contient : les 6 questions FR pretes a coller, la regle de combinaison
`addressed_v2`, et la mesure. Ne reinvente rien, applique-la.

Resultat mesure a reproduire : 0 faux negatif sur 24 phrases adressees,
0 faux positif sur 22 phrases non adressees. La version actuelle fait 2 et 2.

## Perimetre STRICT
- `src/ears/jev_reflexe.py`
- `src/i18n/__init__.py` (QUESTIONS_EN uniquement — traduis les 6 questions)
- `dev/scripts/serve_hostagent.py` (point de decision uniquement)
- `dev/tests/test_jev_v2.py` (a creer)

INTERDIT : `native/*`, `src/mouth/*`, `src/brain/*`, `.env.local`.
N'EXECUTE AUCUNE COMMANDE GIT.

## Travail
1. Remplace le dictionnaire `QUESTIONS` de `src/ears/jev_reflexe.py` par les 6
   questions de la source. Garde les autres questions existantes
   (`real_interruption`, `phrase_finished`, etc.) : elles servent ailleurs.
   ATTENTION : `_validated_answers` exige que les reponses recues correspondent
   EXACTEMENT au jeu de questions envoye (`set(raw_answers) != set(QUESTIONS)`).
   Verifie que ca reste coherent, sinon tout appel rendra None silencieusement.
2. Implemente la regle `addressed_v2` comme une FONCTION PURE testable dans
   `src/ears/jev_reflexe.py`, avec les seuils de la source en constantes nommees
   et commentees.
3. `JevSignals.addressed_to_mother` doit desormais etre calcule par cette regle.
   Le reste du produit ne doit RIEN avoir a changer : `jev_ignore_tour` et
   `jev_doit_ignorer` continuent de lire `signals.addressed_to_mother`.
4. Traduis les 6 questions en anglais dans `QUESTIONS_EN`. L'espagnol est
   REPORTE, ne t'en occupe pas.
5. Ne touche NI au filtre local `nom_du_produit_prononce` NI a
   `FenetreConversation` : ils restent, ils couvrent les deformations ASR a
   latence nulle et la conversation en cours.

## Tests — `dev/tests/test_jev_v2.py`
AUCUN appel reseau. Fabrique des dictionnaires de reponses et verifie la regle :
- nom prononce seul (>= 0.50) -> adresse, meme si tout le reste est bas
- interpellation forte sans nom -> adresse
- demande forte sans nom -> adresse
- interpellation forte MAIS conversation avec un tiers elevee -> NON adresse
- parole rapportee elevee -> NON adresse
- contenu diffuse/lu eleve -> NON adresse
- tout bas -> NON adresse
- chaque seuil est teste juste en dessous et juste au-dessus

## Preuve
    docker exec mother-core-dev sh -c "cd /workspace && python -m pytest -q dev/tests/test_jev_v2.py dev/tests/test_jev_reflexe.py dev/tests/test_jev_seuil_et_nom.py dev/tests/test_fenetre_conversation.py dev/tests/test_jev_branchement.py"
OUT dans `nights/2026-09-20-OUT-JEV-V2-POSE.md`. Ne reponds que OK.
