# Calibrage du seuil JeV — mesure API reelle

Mesure executee le 2026-09-20 dans `mother-core-dev`, avec
`PYTHONPATH=/workspace` et le client applicatif `JevReflexe`. La cle a ete lue
localement depuis `.env.local` par le banc et n'apparait ni ici ni dans sa
sortie. Chaque phrase a fait l'objet d'un appel JeV et le score releve est
`addressed_to_mother.noul`.

## Scores

| Jeu attendu | Phrase | Score |
|---|---|---:|
| adressee | Hyper Ambient | 0.39 |
| adressee | oui ? | 0.58 |
| adressee | stop | 0.63 |
| adressee | attends | 0.19 |
| adressee | quelle heure est-il ? | 0.59 |
| adressee | dis-moi l'heure | 0.66 |
| adressee | tu m'entends ? | 0.60 |
| adressee | est-ce que tu m'entends ? | 0.68 |
| adressee | Hyper Ambient, tu m'entends ? | 0.90 |
| adressee | peux-tu regarder la meteo a Marseille ? | 0.84 |
| adressee | donne-moi la capitale du Japon | 0.82 |
| adressee | rappelle-moi d'appeler Lea demain matin | 0.75 |
| adressee | mets une minuterie de cinq minutes | 0.68 |
| adressee | Hyper Ambient, explique-moi la photosynthese | 0.96 |
| adressee | cherche un restaurant vegetarien pres d'ici | 0.75 |
| adressee | MOTHER, annule la derniere demande | 0.96 |
| non adressee | bon alors on disait le module deux | 0.15 |
| non adressee | attends deux secondes je parle a quelqu'un d'autre | 0.10 |
| non adressee | tu prends le train de 18 heures ou celui de 19 heures ? | 0.31 |
| non adressee | non, je pense qu'on devrait reporter la reunion a lundi | 0.23 |
| non adressee | je t'envoie le document apres le dejeuner | 0.34 |
| non adressee | la recette dit de laisser mijoter pendant vingt minutes | 0.06 |
| non adressee | dans le chapitre trois, le personnage quitte enfin Paris | 0.04 |
| non adressee | il etait une fois une petite fille qui vivait dans la foret | 0.02 |
| non adressee | voyons, si je divise par douze ca fait combien deja | 0.16 |
| non adressee | il faut que je pense a acheter du cafe en rentrant | 0.04 |
| non adressee | ah non, j'ai oublie mes cles sur la table | 0.08 |
| non adressee | ce soir dans le journal, la circulation reste difficile sur le peripherique | 0.03 |
| non adressee | la meteo annonce des averses sur la moitie nord du pays | 0.03 |
| non adressee | et maintenant, place au film de la soiree sur votre chaine | 0.55 |
| non adressee | oui je suis d'accord avec toi, on fait comme ca | 0.29 |
| non adressee | passe-moi le sel, s'il te plait | 0.41 |

## Erreurs par seuil

Une phrase est acceptee lorsque son score est superieur ou egal au seuil.
Les faux negatifs sont les phrases adressees ignorees ; les faux positifs sont
les phrases non adressees qui declencheraient l'assistante.

| Seuil | Faux negatifs | Faux positifs |
|---:|---:|---:|
| 0.20 | 1 | 6 |
| 0.25 | 1 | 5 |
| 0.30 | 1 | 4 |
| 0.35 | 1 | 2 |
| 0.40 | 2 | 2 |
| 0.45 | 2 | 1 |
| 0.50 | 2 | 1 |
| 0.55 | 2 | 1 |
| 0.60 | 4 | 0 |
| 0.65 | 6 | 0 |
| 0.70 | 9 | 0 |
| 0.75 | 9 | 0 |
| 0.80 | 11 | 0 |

## Recommandation : `JEV_NOUL_TRUE_THRESHOLD=0.60`

`0.60` est le seuil le plus bas qui ne produit aucun faux positif dans ce
corpus. C'est donc le meilleur arbitrage pour une demonstration : abaisser a
`0.55` recupere deux phrases adressees, mais ferait repondre l'assistante a la
phrase de television en fond (« et maintenant, place au film... », score
`0.55`). Ce type de declenchement parasite est explicitement plus dommageable
qu'une ignorance ponctuelle.

Par rapport au seuil actuel `0.75`, `0.60` fait passer cinq phrases adressees
supplementaires sans ouvrir de faux positif mesure : « oui ? », « stop »,
« quelle heure est-il ? », « tu m'entends ? » et « dis-moi l'heure ». Les quatre
faux negatifs restants sont « Hyper Ambient » seul, « attends » seul, « oui ? »
et « quelle heure est-il ? » ; les deux derniers restent juste sous le seuil
pour les scores mesures de `0.58` et `0.59`.

Le nom du produit prononce seul et « attends » restent donc des cas limites a
ameliorer dans les criteres ou dans un jeu de mesures ulterieur, plutot qu'une
raison d'abaisser le seuil et de reintroduire un faux declenchement de TV.
