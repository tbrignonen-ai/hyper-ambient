# BRIEF Codex — repenser les questions posees a JeV
Lead : Claude (Opus). 2026-09-20 ~20h. URGENT.

## Le reproche de l'utilisateur, mot pour mot
« Ca va pas du tout vos questions a JeV, mettez plus de criteres, ca coute rien,
et adaptez-les bien au use case precisement. Ne mettez pas tout dans une seule
question fourre-tout. Apprenez a utiliser JeV. »

Il a raison. Aujourd'hui, TOUTE la decision « est-ce que ca m'est adresse » tient
dans UNE question (`addressed_to_mother`), dont les criteres ont ete elargis a
la main jusqu'a devenir un fourre-tout. Resultat mesure : « est-ce que tu
m'entends ? » et « hyper ambiant » seul ne declenchent pas de facon fiable.

## Ce qu'est JeV
API typesafe.ai (`POST https://api.typesafe.ai/v1/systemone`), modele `jev-latest`.
On envoie `{"state": {"transcription": ...}, "model": ..., "questions": {...}}`.
Chaque question a un `type` (`noul` = degre de verite entre 0 et 1, `choice`,
`score`), des `instructions` et des `criteria` {true, false}.
Les questions actuelles sont dans `src/ears/jev_reflexe.py` (QUESTIONS, francais)
et `src/i18n/__init__.py` (QUESTIONS_EN, anglais). Lis-les avant de proposer.

POINT CLE : poser PLUSIEURS questions dans le meme appel ne coute rien de plus
(un seul aller-retour HTTP). On peut donc decomposer largement.

## Ta mission
Concevoir un JEU DE QUESTIONS DECOMPOSE qui remplace la question fourre-tout.
Piste a instruire (tu es libre de faire mieux, argumente) :
- une question « la personne INTERPELLE-t-elle quelqu'un ? » (he, salut, bonjour,
  coucou, allo, un prenom, un nom d'assistant)
- une question « la personne formule-t-elle une DEMANDE ou un ORDRE ? »
  (question, imperatif, requete)
- une question « la personne parle-t-elle a UN TIERS PRESENT ? » (conversation)
- une question « est-ce du contenu LU, DIFFUSE ou RECITE ? » (television, radio,
  lecture a voix haute, dictee, generique)
- une question « le nom de l'assistante est-il prononce ? » (tolerer les
  deformations de transcription : hyper ambient / ambiant / ambiance, super
  ambiante, HA, MOTHER)
Puis une REGLE DE COMBINAISON simple et explicite de ces signaux vers la decision
finale « tour adresse : oui / non ».

## Contraintes
- Le produit s'appelle Hyper Ambient. Trois langues : fr, en, es.
- Cle `TYPESAFE_API_KEY` dans `.env.local` : NE L'AFFICHE JAMAIS, ne la recopie
  nulle part.
- Le code tourne DANS `mother-core-dev` :
  `docker exec mother-core-dev sh -c "cd /workspace && PYTHONPATH=/workspace python ..."`
  N'installe rien sur le Python de l'hote.
- MESURE tes propositions contre l'API reelle, sur au moins 20 phrases adressees
  et 20 non adressees, en francais. Utilise les phrases reelles ci-dessous, qui
  ont echoue aujourd'hui :
    « est-ce que tu m'entends ? », « hyper ambiant », « bonjour », « salut »,
    « hey », « bon je teste le mode mains libres, bonjour », « tu m'entends ? »
  et les pieges : « et maintenant place au film de la soiree »,
  « Realise par Neo035 Avec le soutien de SWIT Airsoft »,
  « bon alors on disait le module deux », « je t'envoie le document apres le dejeuner ».
- NE MODIFIE AUCUN FICHIER DE PRODUCTION. Tu proposes et tu mesures.
- N'EXECUTE AUCUNE COMMANDE GIT.

## Livrable
`nights/2026-09-20-OUT-JEV-QUESTIONS-V2.md` : le jeu de questions complet en
francais pret a coller, la regle de combinaison, le tableau des scores mesures,
et le taux de faux positifs / faux negatifs compare a la version actuelle.
