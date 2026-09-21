# Fluidité Codex — 20 septembre 2026

Périmètre modifié : `dev/scripts/serve_hostagent.py`, `src/brain/mandat.py`,
`src/ears/silence.py` et les tests associés. Les répertoires interdits n'ont pas
été modifiés.

## 1. Mandat vide

Le journal confirme le dépôt inutile : après « Oui mais je voudrais que tu
demandes à Codex », le pont a reçu une question vide ou sans objet et a répondu
qu'il attendait une question.

`deposer_depuis_outil` valide désormais la charge juste avant de créer le
mandat, donc pour Codex comme pour Claude et les autres consommateurs du même
chemin. La validation est structurelle (longueur minimale, deux mots, et un
sujet réel si un harnais est nommé), et non une liste de mots-clés. Un geste
sans question ne crée ni tâche ni appel réseau et répond : « Que veux-tu que je
demande à Codex ? ».

Tests : question vide, simple nom de harnais, demande sans sujet, question
courte réelle, et absence d'appel du pont.

## 2. Expiration du contexte outil

Le buffer brut `_dernier_outils` expirait bien après une reprise, mais la
réponse vocale issue de l'outil restait dans `_historique`. C'est ce qui pouvait
réancrer les tours ultérieurs sur la météo même sans balise « résultat outil ».

Les deux messages de l'échange qui a produit un outil sont maintenant marqués
éphémères. Le tour suivant reçoit encore la réponse et le résultat brut ; dès
que cette copie de l'historique a été constituée, les deux sont purgés pour les
tours suivants. Le test d'expiration vérifie à présent, deux tours après
l'outil, l'absence de la balise brute **et** du contenu « neuf fichiers » dans
la requête réellement remise au modèle. Cette dernière assertion échouait avec
l'ancien comportement, car la réponse assistant demeurait dans l'historique.

## 3. Arrivée de mandat

Le journal historique ne permet pas de dire si l'annonce a été jouée : il ne
contenait que `MANDAT: arrivee`, sans trace de synthèse ni d'envoi. Il ne permet
donc pas d'attribuer rétrospectivement la perte à la parole simultanée, au
marqueur de fin ou au lecteur hôte.

Le prochain essai tranche la partie serveur avec trois traces corrélées par
identifiant : `annonce emission` (nombre de trames et durée, après le
`send_json`), puis `annonce fin_envoyee`; ou `annonce audio_vide` / `annonce
echec`. Sans accusé de lecture dans le protocole hôte, le serveur ne peut pas
prouver physiquement le haut-parleur, mais il distingue désormais synthèse
vide, échec d'émission et émission acceptée par le WebSocket. Une synthèse vide
ou une exception ne marque plus le mandat comme annoncé : il reste prêt au lieu
d'être silencieusement perdu. Un test fige ce cas.

## 4. Hallucination Whisper sur silence

Le filtre d'énergie pré-ASR déjà présent reste le garde-fou principal : il
évite l'inférence sur les segments sous -50 dBFS. Une seconde barrière,
volontairement très étroite, rejette après transcription le crédit exact observé
sur la machine (`Sous-titrage ST' 501`, normalisé accents et apostrophes). Elle
protège le cas où du bruit parasite dépasse le seuil d'énergie. Le segment est
clos sans BRAIN ni parole ; il ne devient donc pas un tour de conversation.

Tests : variantes du crédit, phrase normale non rejetée, et intégration où
l'artefact ne parvient pas à BRAIN.

## Vérification

Commande exécutée :

```text
docker exec mother-core-dev python -m pytest dev/tests -q --ignore=dev/tests/test_health_sondes.py
```

Résultat : **1423 passed, 4 failed, 56 skipped, 2 xfailed**. Les quatre échecs
préexistants sont tous hors périmètre et dus à l'absence de `tkinter` dans le
conteneur (`native/presence/*`). Aucun échec nouveau.

Les correctifs ont aussi été exercés isolément : **108 passed**
(`test_mandat`, `test_outils_voix`, `test_ears_silence`, `test_tools_codex`,
`test_tools_cli`).
