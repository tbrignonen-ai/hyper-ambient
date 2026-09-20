1. `suspended_times`

```yaml
search:
  suspended_times:
    SearxEngineAccessDenied: 3600
    SearxEngineCaptcha: 3600
    SearxEngineTooManyRequests: 600
    cf_SearxEngineCaptcha: 1296000
    cf_SearxEngineAccessDenied: 86400
    recaptcha_SearxEngineCaptcha: 604800
```

- Oui, vos valeurs actuelles (`86400`, `1296000`, …) sont les valeurs par défaut de SearXNG.
- Pour une instance personnelle à faible trafic, réduisez uniquement les suspensions « standards » (`AccessDenied`, `Captcha`, `TooManyRequests`) pour retrouver plus vite des résultats, mais **gardez Cloudflare long** (15 jours). Retourner trop tôt devant Cloudflare aggrave presque toujours le ban (blocage IP prolongé, challenge renforcé).
- Risque d’abaisser globalement : chaque retour prématuré sur un moteur qui vient de vous sanctionner augmente la durée du ban suivant ; sur Cloudflare/Startpage cela peut aboutir à un blocage IP de plusieurs jours, voire définitif selon l’ASN.

---

2. `outgoing`

```yaml
outgoing:
  request_timeout: 5.0
  useragent_suffix: ""
  pool_connections: 100
  pool_maxsize: 50
  enable_http2: true
  proxies: []
```

- `request_timeout` : `3.0` est trop court pour les moteurs « lents » (Wolfram, Startpage, etc.). `5.0` est un bon compromis latence/résilience ; `8.0` si votre réseau est lent ou si vous acceptez une latence plus élevée pour l’assistant vocal.
- `retries` : **n’existe pas** dans la section `outgoing` de SearXNG. Ne l’ajoutez pas, le schéma le rejettera.
- `useragent_suffix` : laissez `""`. Ne simulez pas un UA navigateur standard ; SearXNG s’annonce déjà comme bot. Un suffixe « contact » peut aider sur certains moteurs, mais devient inutile si l’instance n’a pas d’URL publique.
- `proxies` : le seul levier réel contre les bannissements IP. Exemple avec rotation :
  ```yaml
  outgoing:
    request_timeout: 5.0
    useragent_suffix: ""
    pool_connections: 100
    pool_maxsize: 50
    enable_http2: true
    proxies:
      - "socks5h://127.0.0.1:9050/"
      - "http://10.0.0.5:3128"
  ```
- `enable_http2` : conservez `true` (défaut). Le passer à `false` peut « aider » face à certains détecteurs de TLS fingerprinting, mais réduit les performances.
- `pool_maxsize` : `20` suffit pour un usage machine ; `50` laisse de la marge si vous ajoutez des moteurs.

---

3. `limiter` et `public_instance`

```yaml
limiter:
  enable: false
```

```yaml
server:
  public_instance: false
  method: "GET"
```

- `limiter: true` limite par IP + empreinte. Votre conteneur voisin a une IP Docker stable : dès qu’il dépasse `rate`/`burst`, SearXNG renvoie `429`. **Oui, le limiter peut bloquer votre propre client JSON**, et c’est probablement un facteur de latence/disponibilité même s’il n’explique pas le `results: []`.
- `public_instance: false` ne désactive pas le limiter ; il change seulement le comportement UI (liens publics, etc.).
- Pour un usage machine sur réseau privé Docker, désactivez le limiter. Si vous voulez le garder par principe, montez les seuils :
  ```yaml
  limiter:
    enable: true
    rate: 60
    burst: 200
  ```
- `server.method: "POST"` n’affecte pas les requêtes `GET /search?format=json`, mais le passer à `"GET"` évite tout ambiguïté avec des reverse-proxy ou clients stricts.

---

4. FORMAT JSON : conditions et pièges

- L’API JSON exige `formats: [json]` dans `search.formats` (déjà présent).
- Le client doit appeler `GET /search?q=...&format=json`. Pas de session ni de CSRF requis.
- Pièges connus :
  - `display_type: ["infobox"]` sur `wikipedia` et `wikidata` : ces moteurs ne renvoient **plus rien dans `results`**, seulement dans `infoboxes`. Si les autres moteurs sont suspendus, `results` reste vide alors qu’une infobox est présente. Corrigez si vous voulez des résultats web classiques :
    ```yaml
    - name: wikipedia
      engine: wikipedia
      shortcut: wp
      display_type: ["infobox", "result"]
    ```
  - `number_of_results: 0` avec HTTP 200 signifie « tous les moteurs de la catégorie sont muets ou suspendus ». Le client doit toujours inspecter `unresponsive_engines`.
  - `default_lang: "auto"` fonctionne, mais si vous envoyez `language` explicitement (ex: `lang=fr`), seuls les moteurs qui supportent cette langue répondent.
  - Si vous placez un reverse-proxy devant SearXNG avec `base_url: false`, les URLs de résultats peuvent être relatives ; mettez `base_url: "https://votre-domaine/"` si besoin.

---

5. Observer les blocages

```yaml
general:
  enable_metrics: true
  open_metrics: "atlas-local-metrics-token"
```

```yaml
checker:
  off_when_debug: true
```

- **Logs Docker** : `docker logs -f <conteneur>` puis filtrez sur `[!] engine`. Activez temporairement `general.debug: true` pour voir les URLs et réponses brutes des moteurs (attention aux secrets dans les logs).
- **Métriques** : renseignez `open_metrics` avec un token, puis interrogez :
  ```bash
  curl "http://127.0.0.1:8080/metrics?token=atlas-local-metrics-token"
  ```
  Vous y verrez les compteurs d’erreurs par moteur et les suspensions actives.
- **`unresponsive_engines`** : la réponse JSON contient déjà la liste `[engine, reason]` ; c’est votre meilleur indicateur temps réel.
- **Checker** : si vous voulez forcer un diagnostic manuel des moteurs, lancez-le dans le conteneur (chemin indicatif selon l’image) :
  ```bash
  docker exec -it <conteneur> /usr/local/searxng/venv/bin/python -m searx.checker
  ```