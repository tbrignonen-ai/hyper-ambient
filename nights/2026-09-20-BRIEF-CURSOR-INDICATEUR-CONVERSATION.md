# BRIEF Cursor — indicateur visuel d'etat de conversation
Lead : Claude (Opus). 2026-09-20 ~20h30.

## Specification de l'utilisateur, mot pour mot
« En mode mains libres (seul cas ou JeV est utilise), JeV ne sert qu'a lancer le
mode. Une fois la conversation lancee il n'intervient plus du tout. Juste un
silence assez long (30 secondes) la termine. Il faut un indicateur sur l'appli. »

## Ce qui existe deja (ne le refais pas)
- `src/ears/jev_reflexe.py` : classe `FenetreConversation` (defaut 30 s),
  methodes `engager()`, `engagee()`, `fermer()`.
- `dev/scripts/serve_hostagent.py` : la fenetre est ouverte quand le tour est
  juge adresse, et refermee quand le mains libres s'eteint. Tant qu'elle est
  ouverte, JeV n'est PAS appele (log `JEV : conversation en cours`).
- Presence recoit deja `{"type":"jev_pret"}` et affiche « Mains libres pretes. ».

## Ce qui manque : l'utilisateur ne VOIT pas dans quel etat il est
Trois etats a distinguer a l'oeil :
1. mains libres ETEINT
2. mains libres ALLUME mais conversation FERMEE — elle filtre, il faut
   l'interpeller (dire son nom, « bonjour », « hey »…)
3. conversation OUVERTE — elle ecoute tout, plus de filtrage, et il reste N
   secondes avant fermeture

## Perimetre STRICT
- `dev/scripts/serve_hostagent.py` : EMISSION du nouveau message uniquement
- `native/presence/app.py` : RECEPTION et affichage
- `src/i18n/__init__.py` : libelles fr / en / es
- `dev/tests/test_indicateur_conversation.py` (a creer)

INTERDIT : `src/ears/*`, `src/mouth/*`, `native/hostagent/*`, `.env.local`.
N'EXECUTE AUCUNE COMMANDE GIT.

## Travail
1. Host-agent : emettre `{"type": "conversation", "ouverte": true|false,
   "restant_s": <float>}` a chaque changement d'etat, ET un rafraichissement
   periodique tant que la conversation est ouverte (une fois par seconde suffit)
   pour que le decompte vive. Reutilise le canal WebSocket existant.
2. Presence : afficher l'etat. Sobre et lisible — c'est une presence ambiante,
   pas un tableau de bord. Une pastille de couleur plus un texte court suffit.
   Reutilise la palette existante (`visuel.PALETTES`) : « ecoute » quand la
   conversation est ouverte, « repos » sinon. Respecte le contraste
   (`self.configuration.contraste`), il est deja gere ailleurs dans ce fichier.
3. Libelles fr / en / es, nouvelles cles dans `ui_presence()`. Suggestions FR :
   « En conversation — 24 s », « Dis mon nom pour me parler », et rien du tout
   quand le mains libres est eteint.
4. Quand la conversation se referme, l'indicateur doit revenir a l'etat 2 tout
   seul, sans action de l'utilisateur.

## Tests
Harnais `_application(tmp_path, ...)` de `dev/tests/test_presence_stop_mains_libres.py`.
Couvre : reception de `conversation ouverte=true` -> libelle attendu ; `false` ->
libelle d'invitation ; mains libres OFF -> aucun des deux ; le decompte s'affiche.

## Preuve
Sur l'HOTE Windows (tkinter absent du conteneur) :
    python -m pytest -q dev/tests/test_indicateur_conversation.py dev/tests/test_presence_connexion_jev.py dev/tests/test_presence_stop_mains_libres.py
Puis dans le conteneur :
    docker exec mother-core-dev sh -c "cd /workspace && python -m pytest -q dev/tests/test_hostagent_transport.py dev/tests/test_fenetre_conversation.py"
OUT dans `nights/2026-09-20-OUT-INDICATEUR-CONVERSATION.md`. Ne reponds que OK.
