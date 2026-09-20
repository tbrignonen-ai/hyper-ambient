1. DIAGNOSTIC

- **Pourquoi ces cinq moteurs tombent**
  - `duckduckgo`, `startpage`, `mojeek`, `yep` reposent sur du **scraping HTML protégé** (reCAPTCHA, Cloudflare, bannissement IP comportemental). Sur une IP résidentielle non réputée, ils sont bannis en quelques requêtes.
  - `wolframalpha_noapi` fait du scraping d’un site lourd en JS : timeout à 3 s (`outgoing.request_timeout`). Sans clé API il est inutilisable.
  - Votre `suspended_times` à **86400 s** (24 h) pour CAPTCHA/AccessDenied transforme un échec temporaire en mort définitive pour la journée.

- **Pourquoi Google et Qwant survivent**
  - **Google** : SearXNG scrape les résultats organiques ; Google tolère les requêtes “propres” depuis IP résidentielle à très faible volume.
  - **Qwant** : moteur SearXNG qui interroge une **API JSON interne** (`api.qwant.com`), bien plus permissive que le HTML. Il ne déclenche pas de CAPTCHA immédiat.

- **Robuste vs fragile**
  - **Robuste** : API JSON stable ou quasi-officielle (Qwant, Reddit, GitHub, StackExchange, Wikipedia, DuckDuckGo Instant Answer, Brave API interne, Bing).
  - **Fragile** : scraping HTML avec anti-bot (Startpage, Mojeek, Yep, DuckDuckGo web, WolframAlpha HTML).

- **“python” vs “Marseille”**
  - “python” est couvert par des moteurs API techniques (PyPI, GitHub, StackExchange…) qui ne ban jamais.
  - “meteo Marseille” n’est répondue que par les moteurs web généralistes ; or les SERP météo sont des **widgets dynamiques** (cartes, JS) que SearXNG n’extrait pas en JSON, d’où `results: []`.

2. MOTEURS À RETIRER

| Moteur | Raison |
|---|---|
| `duckduckgo` | Scraping HTML banni/CAPTCHA chronique. |
| `startpage` | Proxy Google avec reCAPTCHA agressif. |
| `mojeek` | Access denied : IP blacklistée. |
| `yep` | Access denied : moteur anti-scraping strict. |
| `wolframalpha_noapi` | Timeout + scraping impossible sans clé API. |
| `google images` | Inutile pour un assistant vocal JSON, consomme des ressources. |

Réduisez aussi les sanctions : mettez `SearxEngineAccessDenied: 600` et `SearxEngineCaptcha: 600` dans `suspended_times`.

3. MOTEURS À AJOUTER

Remplacez intégralement votre bloc `engines:` par ceci :

```yaml
engines:
  - name: google
    engine: google
    shortcut: go
  - name: google news
    engine: google_news
    shortcut: gn
    language: fr
    region: fr-FR
  - name: bing
    engine: bing
    shortcut: bi
  - name: bing news
    engine: bing_news
    shortcut: bn
    language: fr
    region: fr-FR
  - name: brave
    engine: brave
    shortcut: br
    language: fr
    region: fr-FR
  - name: qwant
    engine: qwant
    shortcut: qw
    language: fr
    region: fr-FR
  - name: duckduckgo definitions
    engine: duckduckgo_definitions
    shortcut: dd
  - name: wikipedia
    engine: wikipedia
    shortcut: wp
    display_type: ["infobox"]
  - name: wiktionary
    engine: wiktionary
    shortcut: wt
    display_type: ["infobox"]
  - name: wikidata
    engine: wikidata
    shortcut: wd
    display_type: ["infobox"]
  - name: github
    engine: github
    shortcut: gh
  - name: reddit
    engine: reddit
    shortcut: re
  - name: arxiv
    engine: arxiv
    shortcut: arx
  - name: pypi
    engine: pypi
    shortcut: pypi
  - name: npm
    engine: npm
    shortcut: npm
  - name: docker hub
    engine: docker_hub
    shortcut: dh
  - name: stack exchange
    engine: stackexchange
    shortcut: st
  - name: openstreetmap
    engine: openstreetmap
    shortcut: osm
  - name: youtube
    engine: youtube_noapi
    shortcut: yt
  - name: hackernews
    engine: hackernews
    shortcut: hn
  - name: dailymotion
    engine: dailymotion
    shortcut: dm
```

**Pourquoi ces ajouts**
- `brave` : API interne résiliente, excellents snippets en français.
- `bing` / `bing news` : robustes sur IP résidentielle, indexent bien les boîtes “météo” et l’actualité locale.
- `google_news` : fraîcheur maximale sur `region: fr-FR`.
- `duckduckgo_definitions` : utilise l’API Instant Answer (pas de scraping web), parfait pour les définitions sans CAPTCHA.
- `wiktionary` : définitions francophones structurées.

4. MÉTÉO

Aucun moteur SearXNG natif ne renvoie la météo d’une ville en JSON : les widgets météo de Google/Qwant/Bing ne sont pas scrapés par SearXNG.

**Solution concrète pour l’assistant vocal : contourner SearXNG pour la météo** et appeler directement wttr.in (sans clé, JSON) :

```bash
curl -s "https://wttr.in/Marseille?format=j1" | jq '.current_condition[0] | {temp_C, weatherDesc, humidity, windspeedKmph}'
```

Si vous tenez absolument à passer par SearXNG, il faut écrire un moteur Python custom (`/etc/searx/engines/wttr.py`), ce qui est impossible en YAML seul.

5. VÉRIFICATION

**D’abord corrigez le réseau** : `bind_address: "127.0.0.1"` bloque l’accès depuis un conteneur voisin. Passez à `0.0.0.0` puis redémarrez le conteneur.

Depuis le conteneur voisin (ou l’hôte) :

```bash
# 1. Vérifier l'accessibilité réseau
curl -s "http://<nom_ou_ip_conteneur_searx>:8080/search?q=test&format=json" | jq '.number_of_results'

# 2. Vérifier la disparition des moteurs morts et la présence des nouveaux
curl -s "http://127.0.0.1:8080/search?q=actualite+france&format=json&engines=google_news,bing_news,qwant,brave" | jq '.number_of_results, .unresponsive_engines'

# 3. Vérifier une requête factuelle sensible (météo / locale)
curl -s "http://127.0.0.1:8080/search?q=meteo+marseille&format=json" | jq '{number: .number_of_results, first: .results[0], unresponsive: .unresponsive_engines}'

# 4. Vérifier le canal météo direct (hors SearXNG)
curl -s "https://wttr.in/Marseille?format=j1" | jq '.current_condition[0].temp_C'
```