# JeV : questions d'adresse V2

Mesure effectuee le 2026-09-20, contre `jev-latest` et l'API reelle depuis
`mother-core-dev`. Aucun fichier de production n'a ete modifie.

La question actuelle melange l'appel, la demande, les tiers et les contenus
diffuses. V2 les separe : les signaux positifs disent *pourquoi* la personne
pourrait nous parler ; les veto disent *pourquoi* elle ne nous parle pas. Les
sept questions restent dans le meme POST System One, donc n'ajoutent aucun
aller-retour.

## Questions FR pretes a coller

Remplacer seulement `addressed_to_mother` par ces identifiants dans le futur
contrat et adapter la validation/signaux a ces sept `noul`.

```python
ADDRESSING_QUESTIONS_V2 = {
    "assistant_name_spoken": {
        "type": "noul",
        "instructions": (
            "Le nom de l'assistante Hyper Ambient est-il prononce ou "
            "manifestement transcrit dans `transcription` ?"
        ),
        "criteria": {
            "true": (
                "Compter Hyper Ambient et deformations ASR proches : "
                "« hyper ambiant », « hyper ambiance », « hyper ambient », "
                "« super ambiante », « HA », « MOTHER ». Le nom seul suffit."
            ),
            "false": (
                "Aucun de ces noms ou variantes n'est prononce. Ne pas deduire "
                "un nom a partir d'un mot isole comme « ambiance » ou « super »."
            ),
        },
    },
    "direct_interpellation": {
        "type": "noul",
        "instructions": (
            "La personne interpelle-t-elle directement un interlocuteur dans "
            "`transcription` ?"
        ),
        "criteria": {
            "true": (
                "Salutation ou appel direct : « bonjour », « salut », « hey », "
                "« he », « coucou », « allo », « ecoute », « dis-moi », ou "
                "vocatif. Compter une salutation seule : sans contexte contraire, "
                "elle interpelle quelqu'un. Compter aussi une formulation "
                "directement a la deuxieme personne."
            ),
            "false": (
                "Pas d'interpellation : narration, phrase descriptive, reflexion "
                "a voix haute, ou paroles echangees de maniere identifiable entre "
                "d'autres personnes."
            ),
        },
    },
    "request_or_command": {
        "type": "noul",
        "instructions": (
            "La personne formule-t-elle a un interlocuteur une demande, une "
            "question ou un ordre dans `transcription` ?"
        ),
        "criteria": {
            "true": (
                "Question attendant une reponse (« est-ce que tu m'entends ? », "
                "« tu peux… ? »), demande, ou imperatif (« cherche », « arrete », "
                "« attends », « donne-moi »)."
            ),
            "false": (
                "Simple affirmation, narration, lecture, phrase inachevee, ou "
                "question rapportee qui ne demande pas de reponse a l'interlocuteur "
                "present."
            ),
        },
    },
    "third_party_conversation": {
        "type": "noul",
        "instructions": (
            "Les paroles sont-elles clairement destinees a une autre personne "
            "presente ou a un tiers, plutot qu'a l'assistante ?"
        ),
        "criteria": {
            "true": (
                "Conversation identifiable entre humains, consigne a un "
                "collegue/proche, ou message destine a un tiers : par exemple "
                "« je t'envoie le document apres le dejeuner », « bon alors on "
                "disait le module deux »."
            ),
            "false": (
                "Aucun tiers identifiable ; une demande ou salutation pourrait "
                "etre pour l'assistante. Le nom Hyper Ambient/MOTHER/HA n'est "
                "jamais un tiers."
            ),
        },
    },
    "read_broadcast_recited": {
        "type": "noul",
        "instructions": (
            "`transcription` est-elle du contenu lu, diffuse ou recite, plutot "
            "qu'une parole spontanee adressee a l'assistante ?"
        ),
        "criteria": {
            "true": (
                "Television, radio, film, publicite, generique/credits, "
                "narration, lecture a voix haute, dictee, paroles de chanson ou "
                "texte recite : par exemple « et maintenant place au film de la "
                "soiree » ou « Realise par… »."
            ),
            "false": (
                "Parole spontanee a un interlocuteur, meme si elle contient une "
                "salutation, une question ou un ordre."
            ),
        },
    },
    "reported_or_quoted_speech": {
        "type": "noul",
        "instructions": (
            "`transcription` rapporte-t-elle, cite-t-elle ou imite-t-elle des "
            "paroles au lieu de les adresser maintenant a l'assistante ?"
        ),
        "criteria": {
            "true": (
                "Paroles rapportees ou citees, par exemple « il a demande : tu "
                "m'entends ? », « elle a dit bonjour », ou une repetition "
                "d'exemple."
            ),
            "false": (
                "La personne prononce elle-meme, maintenant, la salutation, la "
                "question, la demande ou l'ordre pour obtenir une reponse."
            ),
        },
    },
    "unaddressed_self_talk": {
        "type": "noul",
        "instructions": (
            "La personne parle-t-elle sans s'adresser a aucun interlocuteur ?"
        ),
        "criteria": {
            "true": (
                "Reflexion a voix haute, commentaire personnel, monologue ou "
                "constat sans appel, demande ni destinataire."
            ),
            "false": (
                "Elle interpelle quelqu'un, formule une demande/question/ordre, "
                "parle a un tiers, ou lit/diffuse du contenu."
            ),
        },
    },
}
```

Les identifiants et la regle sont communs aux trois langues. Avant activation,
les memes distinctions et exemples doivent etre traduits dans `QUESTIONS_EN`
et dans la table ES a ajouter : ne pas reutiliser les criteres francais pour
une transcription anglaise ou espagnole. La mesure ci-dessous ne couvre que le
francais.

## Regle de combinaison

Soit `s(id)` le `noul` de la reponse. Le nom explicite est une invocation a lui
seul. Sans nom, il faut au moins une interpellation ou une demande, et aucun
veto fort. Cette regle conserve volontairement les salutations seules : le
produit prefere repondre a un « bonjour » plutot que l'ignorer.

```python
def addressed_v2(a: Mapping[str, Mapping[str, float]]) -> bool:
    s = lambda name: float(a[name]["noul"])
    return (
        s("assistant_name_spoken") >= 0.50
        or (
            (s("direct_interpellation") >= 0.55
             or s("request_or_command") >= 0.50)
            and s("third_party_conversation") < 0.55
            and s("read_broadcast_recited") < 0.65
            and s("reported_or_quoted_speech") < 0.50
            and s("unaddressed_self_talk") < 0.70
        )
    )
```

`MOTHER` et `HA` doivent aussi rester soumis au filtre local existant si celui-ci
est conserve : JeV donne la decision linguistique, le filtre local couvre les
variantes ASR a latence nulle.

## Mesure reelle

Jeu etiquete manuellement : 24 tours adresses, 22 non adresses (46 au total).
La colonne actuelle est `addressed_to_mother`, seuil de production `0.60`.
Pour V2, les scores sont dans l'ordre `N/I/D/T/L/R/S` : nom, interpellation,
demande, tiers, lu/diffuse, rapporte/cite, monologue. `oui`/`non` est la regle
ci-dessus. Les scores sont une passe API, donc a revalider sur un corpus plus
large avant mise en production.

| Attendu | Transcription | Actuel | V2 N/I/D/T/L/R/S | V2 |
|---|---|---:|---|---|
| oui | est-ce que tu m'entends ? | 0.92 | .02/.95/.99/.35/.10/.11/.02 | oui |
| oui | hyper ambiant | 0.76 | .95/.03/.03/.09/.52/.21/.77 | oui |
| oui | bonjour | 0.89 | .02/.95/.02/.17/.15/.12/.12 | oui |
| oui | salut | 0.88 | .03/.96/.02/.24/.14/.09/.11 | oui |
| oui | hey | 0.90 | .02/.96/.03/.20/.09/.08/.13 | oui |
| oui | bon je teste le mode mains libres, bonjour | 0.87 | .03/.88/.06/.15/.11/.12/.42 | oui |
| oui | tu m'entends ? | 0.92 | .02/.96/.96/.44/.12/.14/.02 | oui |
| oui | Hyper Ambient, quelle heure est-il ? | 0.95 | .93/.89/.96/.09/.21/.14/.12 | oui |
| oui | MOTHER, allume la lumiere | 0.89 | .80/.98/.98/.55/.14/.34/.02 | oui |
| oui | HA, cherche la meteo | 0.95 | .86/.85/.95/.27/.11/.14/.21 | oui |
| oui | coucou Hyper Ambient | 0.96 | .95/.96/.05/.17/.30/.13/.14 | oui |
| oui | dis-moi la temperature | 0.94 | .03/.98/.97/.18/.08/.08/.03 | oui |
| oui | arrete | 0.82 | .03/.59/.97/.30/.28/.18/.17 | oui |
| oui | attends | 0.75 | .03/.07/.53/.25/.51/.40/.65 | oui |
| oui | peux-tu noter que mon rendez-vous est mardi ? | 0.95 | .03/.95/.98/.11/.06/.07/.02 | oui |
| oui | quel temps fera-t-il demain ? | 0.51 | .02/.20/.98/.08/.10/.07/.11 | oui |
| oui | ouvre le calendrier | 0.93 | .03/.49/.96/.11/.09/.07/.13 | oui |
| oui | aide-moi avec ce document | 0.91 | .03/.87/.97/.11/.08/.06/.04 | oui |
| oui | je voudrais une recette de risotto | 0.58 | .02/.21/.89/.05/.06/.05/.08 | oui |
| oui | ecoute, j'ai une question | 0.91 | .03/.97/.70/.30/.06/.09/.03 | oui |
| oui | bonsoir | 0.88 | .02/.94/.02/.20/.14/.09/.13 | oui |
| oui | allo ? | 0.82 | .02/.96/.71/.30/.11/.13/.10 | oui |
| oui | reponds-moi | 0.91 | .03/.95/.97/.22/.10/.10/.03 | oui |
| oui | tu peux repeter ? | 0.88 | .03/.94/.98/.28/.06/.08/.02 | oui |
| non | et maintenant place au film de la soiree | 0.07 | .03/.11/.28/.45/.83/.16/.30 | non |
| non | Realise par Neo035 Avec le soutien de SWIT Airsoft | 0.02 | .03/.03/.02/.18/.97/.35/.56 | non |
| non | bon alors on disait le module deux | 0.13 | .02/.34/.06/.70/.19/.55/.42 | non |
| non | je t'envoie le document apres le dejeuner | 0.61 | .02/.82/.04/.77/.07/.14/.04 | non |
| non | le train part a huit heures | 0.04 | .02/.03/.02/.39/.35/.19/.73 | non |
| non | il fait beau aujourd'hui | 0.04 | .02/.03/.02/.19/.22/.13/.81 | non |
| non | je pense que je vais prendre du pain | 0.05 | .02/.03/.03/.21/.14/.14/.84 | non |
| non | la prochaine chanson est dediee a Marie | 0.03 | .08/.05/.02/.88/.56/.19/.45 | non |
| non | dans le chapitre trois, le heros ouvre la porte | 0.03 | .02/.02/.02/.23/.68/.27/.71 | non |
| non | repetez apres moi : bonjour tout le monde | 0.27 | .03/.87/.96/.33/.69/.68/.03 | non |
| non | Julie, tu peux fermer la fenetre ? | 0.17 | .05/.99/.98/.78/.07/.19/.01 | non |
| non | salut Marc, ca va ? | 0.07 | .03/.99/.95/.84/.09/.31/.01 | non |
| non | je vais appeler maman ce soir | 0.05 | .03/.04/.03/.43/.15/.18/.78 | non |
| non | ce soir dans votre journal, les titres | 0.05 | .02/.42/.04/.42/.91/.39/.20 | non |
| non | abonnez-vous et activez la cloche | 0.12 | .02/.64/.97/.43/.79/.22/.05 | non |
| non | il a demande : tu m'entends ? | 0.77 | .02/.87/.60/.50/.28/.98/.02 | non |
| non | la meteo annonce de la pluie demain | 0.05 | .02/.03/.02/.25/.35/.54/.78 | non |
| non | je dois repondre a ce mail | 0.06 | .03/.03/.04/.18/.14/.12/.82 | non |
| non | on se retrouve a dix heures | 0.18 | .02/.27/.14/.67/.17/.18/.14 | non |
| non | merci a tous d'etre venus | 0.05 | .03/.56/.03/.58/.35/.21/.04 | non |
| non | bonjour et bienvenue dans cette emission | 0.18 | .03/.92/.03/.49/.92/.19/.11 | non |
| non | le professeur a dit d'ouvrir le livre | 0.03 | .02/.04/.09/.45/.39/.96/.73 | non |

## Comparaison

| Version | Faux negatifs | Taux FN | Faux positifs | Taux FP |
|---|---:|---:|---:|---:|
| Actuelle, seuil 0.60 | 2/24 | 8.3 % | 2/22 | 9.1 % |
| V2, regle ci-dessus | 0/24 | 0.0 % | 0/22 | 0.0 % |

Les deux erreurs actuelles sont « quel temps fera-t-il demain ? » (0.51) et
« je voudrais une recette de risotto » (0.58), alors que les deux faux positifs
sont la phrase a un tiers « je t'envoie le document… » (0.61) et la parole
rapportee « il a demande : tu m'entends ? » (0.77). V2 les explique par des
signaux distincts plutot que d'elargir encore une unique consigne.
