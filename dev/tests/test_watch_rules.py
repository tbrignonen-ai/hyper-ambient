"""
Tests de la règle d'expiration de délégation (REQ-D3-03).

Forme d'événement retenue, cohérente avec test_watch.py : un dict
portant au moins `kind` (genre) et `silence_s` (durée de silence
en secondes, même unité que le `timeout_s` injecté par la fabrique).
Le genre propre à cette règle est `delegation_timeout`. Tout autre
genre, y compris `device_state_changed`, laisse WATCH se taire.
"""


def test_au_dela_du_delai_produit_une_alerte_sobre():
    """Au-delà du délai injecté, la règle lève une alerte sobre D3-AGENTBUS."""
    from src.watch.events import AlertRaised
    from src.watch.rules import delegation_timeout_rule

    regle = delegation_timeout_rule(timeout_s=30)
    evenement = {"kind": "delegation_timeout", "silence_s": 45}
    alerte = regle(evenement)

    assert isinstance(alerte, AlertRaised)
    assert alerte.severity == "sober"
    assert alerte.subject == "delegation_timeout"
    assert alerte.source == "D3-AGENTBUS"


def test_en_deca_du_delai_la_regle_se_tait():
    """En deçà du délai injecté, la règle retourne None : WATCH se tait."""
    from src.watch.rules import delegation_timeout_rule

    regle = delegation_timeout_rule(timeout_s=30)
    evenement = {"kind": "delegation_timeout", "silence_s": 10}
    assert regle(evenement) is None


def test_un_autre_genre_ne_declenche_pas_la_regle():
    """Un autre genre d'événement ne déclenche pas la règle, même au-delà du délai."""
    from src.watch.rules import delegation_timeout_rule

    regle = delegation_timeout_rule(timeout_s=30)
    evenement = {"kind": "device_state_changed", "silence_s": 60}
    assert regle(evenement) is None


def test_watch_publie_selon_le_delai_injecte_sur_le_meme_evenement():
    """Deux délais injectés distincts produisent deux comportements sur le même événement."""
    from src.watch.events import AlertRaised
    from src.watch.policy import Watch
    from src.watch.rules import delegation_timeout_rule

    evenement = {"kind": "delegation_timeout", "silence_s": 45}

    publie_court = []
    watch_court = Watch(
        rules=[delegation_timeout_rule(timeout_s=30)],
        publish=publie_court.append,
    )
    watch_court.observe(evenement)
    assert len(publie_court) == 1
    assert isinstance(publie_court[0], AlertRaised)
    assert publie_court[0].subject == "delegation_timeout"

    publie_long = []
    watch_long = Watch(
        rules=[delegation_timeout_rule(timeout_s=60)],
        publish=publie_long.append,
    )
    watch_long.observe(evenement)
    assert publie_long == []
