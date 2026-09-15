---
date: 2026-09-14
heure: 19:11 Europe/Paris
type: out
auteur: Codex
statut: livre — web_search branche et hostagent relance
hermes: non touche
related:
  - "[[2026-09-13-MUSE-CONNEXIONS]]"
---

# Connexions voix + recherche web — 14 septembre

## Verdict

La voix dispose maintenant de `web_search`. Le hostagent en cours d'execution
annonce au modele un registre non vide :

```text
OUTILS: web_search — porte en mode auto
écoute sur 0.0.0.0:8001 /hostagent
```

SearXNG local est le backend prioritaire, sans cle ni quota. Tavily est garde
comme repli seulement si SearXNG devient injoignable et si `TAVILY_API_KEY`
est configuree.

## Ce qui marche maintenant a la voix

Le chemin produit est desormais :

```text
voix -> construire_registre -> web_search -> SearXNG local -> texte court -> voix
```

- `construire_registre()` enregistre `web_search` avec la seule variable
  `SEARXNG_URL`; aucun jeton CLI n'est requis.
- L'outil reste en `danger="read"`, donc la porte `auto` l'autorise.
- L'annonce deja presente est enfin active : « Je cherche ça sur le web. »
- La reponse SearXNG JSON est transformee en titres + extraits courts, jamais
  en JSON ou URL lus a haute voix.
- L'URL joignable depuis `mother-core-dev` est
  `http://host.docker.internal:8080`. Les conteneurs ne partagent pas le meme
  reseau Docker; le port publie sur l'hote est donc le bon passage.
- `.env.local` contient cette URL et `relancer_routeur.sh` la relit puis
  l'exporte au processus hostagent. `.env.example` documente le meme reglage.

## Preuves du 14 septembre

Depuis `mother-core-dev` :

- endpoint SearXNG : HTTP 200, `Content-Type: application/json`;
- recherche generale `meteo paris` : 16 resultats lors du controle live;
- appel du nouveau handler `SearXNGSearch` : texte court effectivement rendu;
- tests cibles initiaux : `41 passed`;
- regression outils web + boucle vocale : `129 passed in 1.71s`;
- redemarrage par `dev/scripts/relancer_routeur.sh` : hostagent pret, PID 1429;
- log final : `OUTILS: web_search — porte en mode auto` puis écoute sur 8001.

Les moteurs SearXNG externes peuvent etre intermittents (CAPTCHA, timeout ou
access denied observes sur certains moteurs). Une recherche generale a tout de
meme rendu 16 resultats. Si l'instance entiere ne repond plus, le code tente
Tavily lorsqu'une cle est disponible; il ne bascule pas pour un moteur isole.

## Ce qui bloque encore

- `ask_codex` n'est pas dans le registre live : `CODEX_BRIDGE_TOKEN` manque.
- `ask_claude` n'est pas dans le registre live : `CLI_BRIDGE_TOKEN` manque dans
  l'environnement lance par `relancer_routeur.sh`.
- `ask_muse` n'est pas dans le registre live : `MUSE_BRIDGE_URL` n'est pas
  configuree dans ce lancement.
- Tavily n'est pas arme : `TAVILY_API_KEY` manque. Ce n'est pas bloquant tant
  que SearXNG local repond.

Le log ne declare que `web_search`, ce qui prouve a la fois que la recherche web
est disponible et que les connexions CLI restent bloquees par leur configuration,
pas par le registre.

## Garde-fous respectes

- aucun push ni commit;
- aucun `docker compose recreate`;
- aucun changement EARS/TTS ni sample audio;
- Hermes non invoque et non configure.
