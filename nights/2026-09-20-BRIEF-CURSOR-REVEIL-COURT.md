# BRIEF Cursor — reveil court (« Oui ? ») en ecoute continue
Date : 2026-09-20 ~18h50. Lead technique : Claude (Opus).
Ta lane ECOUTE-CONTINUE est validee (8 + 28 tests verifies par moi). Merci.

## Demande de Thomas, mot pour mot
« On detecte qu'il y a un signal audio suffisamment fort pour que ce soit de la voix,
JeV confirme qu'on s'adresse bien a HA, et la HA demande "Oui ?" ou quelque chose de court. »

Aujourd'hui, quand JeV juge le tour adresse, le host-agent envoie le transcript a BRAIN
et fait prononcer une reponse complete. En ecoute continue, cela veut dire qu'une bribe
mal captee recoit une vraie reponse serieuse. Thomas veut un accuse de reception.

## Raffinement impose par le lead (a implementer, ce n'est pas optionnel)
Ne PAS repondre « Oui ? » systematiquement : si le transcript est DEJA une demande
complete, elle repond directement. Sinon chaque echange coute deux tours, ce qui est
penible en demonstration.

Regle : le reveil court se declenche quand JeV dit « adresse a HA » ET que le transcript
n'est pas une demande exploitable. Heuristique LOCALE et gratuite (aucun appel reseau
supplementaire) :
- transcript de moins de 4 mots utiles (hors ponctuation), OU
- transcript qui ne contient que le nom de l'assistante et des mots vides
  (« hyper ambient », « hyper ambiant », « HA », « MOTHER », eventuellement precedes ou
  suivis de « eh », « dis », « hey », « bonjour », « tu es la », etc.)
Ecris cette decision dans une FONCTION PURE testable, pas en ligne dans le pipeline.

## Perimetre STRICT — n'ecris QUE dans ces fichiers
- `src/mouth/secours.py` (ou un module voisin de ton choix DANS src/mouth/) pour les phrases
- `dev/scripts/serve_hostagent.py` pour le cablage
- `dev/tests/test_reveil_court.py` (a creer)

INTERDIT : `native/*` (ta lane precedente est close et validee, n'y retouche pas),
`src/ears/*`, `src/i18n/__init__.py`, `.env.local`.
INTERDIT : lancer Presence, commiter, N'EXECUTE AUCUNE COMMANDE GIT.

## Travail demande

### 1. Fonction pure de decision
Quelque part dans `src/mouth/` :

    def reveil_court_suffit(transcript: str, *, langue: str = "fr") -> bool

True quand le transcript est une interpellation sans demande (voir heuristique ci-dessus).
False quand c'est une vraie demande. Robuste a la casse, aux accents et a la ponctuation.

### 2. Phrases de reveil, FR / EN / ES
Courtes, dans la voix du produit (tutoiement, presence calme — regarde le ton des phrases
existantes dans `secours.py`, aligne-toi dessus). Par exemple FR « Oui ? », « Je t'ecoute. ».
Varie entre deux ou trois formulations pour ne pas donner un effet de robot qui repete.

### 3. Cablage dans `serve_hostagent.py`
Dans le pipeline du tour, APRES que JeV a conclu que le tour est adresse (la ou aujourd'hui
on continue vers BRAIN) :
- si `reveil_court_suffit(transcript)` : prononcer la phrase de reveil et TERMINER le tour.
  **Ne pas appeler BRAIN.** C'est tout l'interet : on economise le cerveau et la latence.
- sinon : comportement actuel inchange, BRAIN repond.
Ce chemin ne doit s'activer QUE si `self._mains_libres` est vrai. En appuyer-pour-parler,
rien ne change : l'utilisateur a appuye, il veut une reponse.
Journalise `JEV   : interpellation sans demande — reveil court`.

### 4. Ne casse pas ce qui existe
`phrase_de_secours` a recu aujourd'hui un parametre `mains_libres` (le silence est muet en
ecoute continue). Ne le defais pas. Le chemin PTT doit rester rigoureusement identique :
c'est le chemin de la demonstration de demain.

## Tests — `dev/tests/test_reveil_court.py`
Aucun reseau, aucun peripherique. Couvre au minimum :
- « hyper ambient » seul -> True ; « Hyper Ambiant ! » -> True ; « MOTHER » -> True
- « hyper ambient, quelle heure est-il ? » -> False
- « dis-moi pourquoi le facteur temps reel doit rester sous 1 » -> False
- « eh hyper ambient » -> True ; « bonjour hyper ambient » -> True
- chaine vide -> True (rien d'exploitable)
- les phrases de reveil existent en fr, en, es et sont courtes (< 30 caracteres)
- non-regression : `phrase_de_secours(transcript="", mains_libres=True)` rend toujours None

## Preuve a rendre
    docker exec mother-core-dev sh -c "cd /workspace && python -m pytest -q dev/tests/test_reveil_court.py dev/tests/test_secours.py"

Colle la sortie telle quelle dans `nights/2026-09-20-OUT-REVEIL-COURT.md`, avec le diff
resume et les difficultes. Ne reponds que OK.
