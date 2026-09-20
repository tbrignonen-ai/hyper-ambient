# BRIEF Codex — calibrage du seuil JeV (mains libres)
Date : 2026-09-20 ~19h. Lead technique : Claude (Opus).

## Constat mesure ce soir, contre l'API reelle
En mains libres, JeV decide si un tour est adresse a l'assistante. Le seuil est
`JevThresholds.noul_true = 0.75` (surchargeable par `JEV_NOUL_TRUE_THRESHOLD`).
Il est TROP STRICT pour les phrases courtes. Mesures (criteres FR actuels) :

  0.40  « Hyper ambient »                          <- le nom du produit, IGNORE
  0.56  « Tu m'entends ? »                          IGNORE
  0.65  « Est-ce que tu m'entends ? »               IGNORE
  0.69  « dis-moi l'heure »                         IGNORE
  0.59  « Est-ce que ca va bien aujourd'hui ? »     IGNORE
  0.81  « Tu peux regarder la meteo a Marseille ? » passe
  0.14  « bon alors on disait le module deux »      ignore (correct)
  0.11  « attends deux secondes je parle a quelqu un d autre » ignore (correct)

La discrimination est bonne (0.11-0.14 pour la conversation autour, 0.40-0.81 pour
l'adresse directe). C'est le curseur qui est mal place.

## Ta mission
Trouver le seuil qui separe le mieux, PAR LA MESURE, pas par intuition.

1. Ecris un script jetable dans `dev/scripts/_calibrage_jev.py` qui interroge l'API
   JeV sur deux jeux de phrases en francais :
   - ADRESSEES (doivent passer) : au moins 15 phrases, dont des tres courtes
     (« Hyper ambient », « oui ? », « stop », « attends »), des questions directes,
     des ordres, avec et sans le nom du produit.
   - NON ADRESSEES (doivent etre ignorees) : au moins 15 phrases de conversation
     entre deux personnes, de texte lu a voix haute, de reflexion a voix haute,
     de television en fond. Sois realiste : c'est ce qu'un micro ouvert capte.
2. Mesure le score `addressed_to_mother.noul` de chacune.
3. Calcule, pour des seuils de 0.20 a 0.80 par pas de 0.05, le nombre de faux
   negatifs (adressee ignoree) et de faux positifs (conversation qui declenche).
4. Recommande UN seuil, en expliquant l'arbitrage. Rappel du contexte produit :
   un faux negatif (elle t'ignore) est frustrant ; un faux positif (elle repond a
   une conversation qui ne la concerne pas) est PIRE et casse une demonstration.

## Contraintes
- La cle est dans `.env.local` sous `TYPESAFE_API_KEY`. NE L'AFFICHE JAMAIS, ne la
  copie dans aucun fichier de sortie.
- Le code tourne DANS le conteneur Docker `mother-core-dev` :
  `docker exec mother-core-dev sh -c "cd /workspace && PYTHONPATH=/workspace python ..."`
  N'installe RIEN sur le Python de l'hote.
- Ne modifie AUCUN fichier de production. Tu produis une mesure et une recommandation.
- N'execute AUCUNE commande git.

## Livrable
`nights/2026-09-20-OUT-CALIBRAGE-JEV.md` : le tableau des scores, le tableau
seuil -> faux negatifs / faux positifs, et ta recommandation argumentee.
