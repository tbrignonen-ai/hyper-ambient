

def test_searxng_lit_answers_et_infoboxes():
    """SearXNG range ses reponses directes hors de `results`.

    Mesure du 2026-09-20 sur l'instance locale : « Marseille » rend
    `results: []` mais une infobox Wikipedia complete, et cinq moteurs
    etaient suspendus (CAPTCHA, access denied). En ne lisant que `answer`
    et `results`, l'outil jetait la seule reponse disponible et l'assistante
    repondait qu'elle n'avait pas acces a internet.

    `answers` et `infoboxes` sont des reponses redigees : ce sont les
    meilleures candidates a la lecture a voix haute, pas un repli.
    """
    from src.brain.tools_web import _speakable

    # Reponse directe : prioritaire sur tout le reste.
    charge = {"answers": ["Marseille compte 870 000 habitants."], "results": []}
    assert "870 000" in _speakable(charge, 3)

    # Infobox seule, sans aucun resultat : doit etre parlee.
    charge = {
        "results": [],
        "infoboxes": [
            {
                "infobox": "Marseille",
                "content": "Marseille est une ville du sud de la France.",
            }
        ],
    }
    parle = _speakable(charge, 3)
    assert "sud de la France" in parle

    # Un vrai resultat reste utilise quand il n'y a ni answer ni infobox.
    charge = {"results": [{"title": "Titre", "content": "Corps"}]}
    assert "Titre" in _speakable(charge, 3)


def test_cascade_distingue_rien_trouve_de_pas_d_acces():
    """« Pas d'acces » ne doit pas masquer « joignable mais rien trouve ».

    La cascade rendait le texte du DERNIER fournisseur essaye. Comme les
    fournisseurs a cle sont en fin de liste et sans cle, une recherche
    SearXNG qui aboutissait sans resultat faisait dire a l'assistante
    « Je n'ai pas encore d'acces a la recherche internet » — un aveu de panne
    alors que la recherche avait fonctionne. Mesure du 2026-09-20 sur
    « meteo Marseille », dont aucun moteur ne rend de resultat exploitable.
    """
    import asyncio
    from src.brain.tools_web import WebSearch, _EMPTY, _NO_KEY

    class Joignable:
        async def search(self, _q):
            return False, _EMPTY

    class SansCle:
        async def search(self, _q):
            return False, _NO_KEY

    # Un fournisseur joignable mais vide l'emporte sur les suivants sans cle.
    w = WebSearch(providers=[Joignable(), SansCle(), SansCle()])
    assert asyncio.run(w("peu importe")) == _EMPTY

    # Aucun fournisseur joignable : l'aveu d'absence de cle reste correct.
    w = WebSearch(providers=[SansCle(), SansCle()])
    assert asyncio.run(w("peu importe")) == _NO_KEY
