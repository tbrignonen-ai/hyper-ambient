# BRIEF Cursor — UI « Connexion… » a l'activation du mains libres
Date : 2026-09-20 ~18h. Lead technique : Claude (Opus). URGENCE BGB.

## Perimetre STRICT — n'ecris QUE dans ces fichiers
- `native/presence/app.py`
- `dev/tests/test_presence_connexion_jev.py` (a creer)

INTERDIT d'ouvrir ou modifier : `src/i18n/__init__.py`, `src/ears/jev_reflexe.py`,
`dev/scripts/serve_hostagent.py`, `src/mouth/*`. Claude y travaille en parallele.
INTERDIT : lancer Presence, commiter, creer une branche, toucher a `.env.local`.

## Contexte mesure (ne pas re-investiguer, c'est etabli)
JeV (filtre « est-ce que ca m'est adresse ») ouvre une connexion TLS distante.
A froid la poignee coute ~600-740 ms et depasse le budget de 600 ms : 3 appels sur 4
expirent. Apres un prechauffage paye hors budget, les appels tombent a 250-300 ms et
reussissent 4 fois sur 4. La connexion reste chaude ~60 s, morte a 90 s.

Decision produit de Thomas : a l'activation du mains libres, on ACCEPTE un delai, et
on l'ANNONCE dans l'appli au lieu de rester muet.

## Travail demande
Dans `native/presence/app.py`, sur `_basculer_mains_libres()` quand on passe a ON :
1. Afficher immediatement le statut `ui_presence()["hands_free_connecting"]`
   (cle deja ajoutee par Claude : FR « Connexion… », EN « Connecting… »).
2. Quand le host-agent confirme que le prechauffage est fini, afficher
   `ui_presence()["hands_free_connected"]` (FR « Mains libres pretes. »).
   Le host-agent enverra un message `{"type":"jev_pret"}` sur le WebSocket —
   Claude cable l'emission de son cote ; toi, cable la RECEPTION et l'affichage.
   Si le message n'arrive pas sous 3 s, afficher quand meme l'etat pret (ne jamais
   laisser l'utilisateur bloque sur « Connexion… »).
3. Pendant « Connexion… », le bouton Parler reste utilisable — on ne bloque rien,
   on informe seulement. Le repli JeV est sur : un tour non evalue n'est pas ignore.
4. Quand on repasse le mains libres a OFF, aucun de ces deux statuts ne doit rester
   affiche.

## Tests (obligatoire, dans le fichier nomme ci-dessus)
Reutilise le harnais de `dev/tests/test_presence_stop_mains_libres.py` (fonction
`_application(tmp_path, mains_libres=...)`). Ecris au minimum :
- bascule ON -> `texte_statut` contient le libelle « Connexion… »
- reception d'un message `{"type":"jev_pret"}` -> statut passe a « Mains libres pretes. »
- bascule OFF -> aucun des deux libelles ne subsiste

## Preuve a rendre
Lance depuis `D:\BGB Training\MOTHER-dev` :
    python -m pytest -q dev/tests/test_presence_connexion_jev.py dev/tests/test_presence_stop_mains_libres.py dev/tests/test_presence_mains_libres.py
ATTENTION : lance-le sur l'HOTE Windows, PAS dans le conteneur Docker — le conteneur
n'a pas `tkinter` et les tests Presence y sont silencieusement inutilisables. C'est
exactement ce qui a produit un « DONE » faux plus tot aujourd'hui.

Ecris le resultat dans `nights/2026-09-20-OUT-JEV-CONNEXION-UI.md` :
le diff resume, la sortie pytest collee telle quelle, et toute difficulte rencontree.
Ne reponds que OK.
