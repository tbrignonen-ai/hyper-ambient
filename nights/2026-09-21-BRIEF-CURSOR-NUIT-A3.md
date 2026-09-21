# Nuit A3 — trois défauts sur le chemin des harnais, vus en conditions réelles

Bon travail sur A2 : la réponse de Codex est enfin une vraie réponse, la question est
reformulée, le canal est juste et l'horodatage est à l'heure de Paris. J'ai vérifié
moi-même, et ma vérification a sorti trois défauts que ton test n'a pas croisés. Même
périmètre, aucune commande git.

## Ce que j'ai exécuté

    docker exec mother-core-dev python dev/scripts/parler_ecrit.py \
      "Demande a Claude Code de me dire quelle version de Python tourne dans ce projet."

    → Codex : Quelle version de Python est utilisée dans ce projet ? Regarde les fichiers
              de configuration (pyproject.toml, setup.py, requirements.txt, runtime.txt,
              .python-version, Dockerfile, etc.) et dis-moi la version exacte.
    ← Codex : Je demande à Codex. Je te préviens dès qu'il répond.
    [deep 2157 ms] Un instant.Je vais demander à Codex de regarder ça pour toi.Je demande
                   à Codex. Je te préviens dès qu'il répond.
    ← Codex : Le projet installe et utilise Python 3.11 exactement. Le Dockerfile
              installe , le définit comme et par défaut.

## Défaut 1 — le harnais nommé n'est pas celui qui est appelé

J'ai dit **Claude Code**, c'est **Codex** qui a été saisi. Le modèle distant a choisi
`ask_codex` alors que l'utilisateur avait désigné un harnais précis.

C'est un défaut de fidélité, pas de goût : quelqu'un qui demande Claude Code a une raison
de le demander — une session ouverte, un contexte déjà chargé, un abonnement. Le produit
ne doit pas substituer silencieusement un outil à un autre.

Corrige de sorte que **le harnais nommé par l'utilisateur fasse autorité**. La table
`_NOMS_VERS_HARNAIS` et `extraire_harnais` dans `src/brain/mandat.py` savent déjà lire le
nom ; ce qui manque est de le faire respecter au moment du choix d'outil. Attention à un
piège de cette table : `cursor` y est mappé sur `Codex`. Vérifie que c'est voulu et
dis-le-moi ; si ça ne l'est pas, ne le change pas sans me le signaler d'abord.

Si le harnais nommé n'est pas configuré, elle doit le **dire** — « Claude Code n'est pas
connecté sur cette machine » — et non basculer sur un autre sans prévenir.

## Défaut 2 — elle annonce trois fois la même chose

    Un instant.Je vais demander à Codex de regarder ça pour toi.Je demande à Codex. Je te
    préviens dès qu'il répond.

Trois annonces d'attente empilées pour un seul tour, et **sans espace entre les phrases**.
Prononcé à voix haute, c'est du bafouillage. Deux choses à corriger :

- **Une seule annonce d'attente par tour.** L'amorce du routeur, la phrase du modèle et
  l'accusé du mandat disent la même chose ; il en faut une. Choisis laquelle porte le sens
  et supprime les autres sur ce chemin, en expliquant ton choix en commentaire.
- **Les morceaux doivent être recollés avec une espace.** Un `Un instant.` suivi
  immédiatement de `Je vais...` se prononce collé. Traite la jointure là où les morceaux
  sont concaténés, pas en ajoutant une espace à la fin de chaque libellé.

Un précédent du projet à ne pas rouvrir : une mesure du 13 septembre a déjà montré que
trois phrases d'attente pour une seule question était un défaut, et le code porte un garde
`est_une_suite_d_outil` pour cela. Regarde pourquoi il ne couvre pas ce cas.

## Défaut 3 — la réponse du harnais perd des mots

    Le Dockerfile installe , le définit comme et par défaut.

Il manque trois fragments, et la phrase devient fausse tout en restant grammaticale —
c'est le pire cas. La cause la plus probable est le nettoyage pour la voix, qui retire le
contenu entre accents graves au lieu de retirer seulement les accents graves.

Trouve la fonction qui nettoie le texte destiné à la parole (`_nettoyer_voix` de
`src/brain/contrat_harnais.py` est un candidat) et corrige-la pour qu'elle **retire le
balisage sans jamais retirer le texte**. Une réponse tronquée silencieusement est plus
dangereuse qu'une réponse mal formatée : à l'oreille, rien ne signale la perte.

Ajoute un test qui vérifie qu'un texte contenant du balisage garde tous ses mots après
nettoyage.

## Tâche 4 — confirmer les quatre tests restants

Ta suite finit à `4 failed, 1476 passed` dans le conteneur, et tu attribues les quatre
échecs à l'absence de `tkinter`. Vérifie-le sur l'hôte Windows, où `tkinter` existe, et
colle la sortie. Si l'un des quatre échoue aussi sur l'hôte, il est réel et il faut le
corriger.

## Vérification attendue

Rejoue les deux commandes, avec **Claude Code** dans l'une d'elles, et colle la sortie
brute. Je veux voir : le bon harnais saisi, une seule annonce d'attente correctement
espacée, et une réponse complète.

Compte rendu dans `nights/2026-09-21-OUT-CURSOR-NUIT-A3.md`.
