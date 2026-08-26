"""
Tests du canal local authentifié entre host-agent et cœur (ADR-016 règle 3).

Le canal est la nouvelle surface d'attaque : local uniquement, secret
partagé, invocations bornées aux quatre primitives du contrat. Pas de
socket, pas de réseau — on teste la logique d'admission.
"""
import pytest


def test_non_local_connection_is_refused_and_shared_secret_is_required():
    """Une adresse non locale est refusée même avec le bon secret ; le secret est exigé en local."""
    from src.hostagent.channel import LocalChannel, ChannelRefused

    secret = "partage-installation"
    canal = LocalChannel(secret=secret)

    canal.authenticate(peer_address="127.0.0.1", secret=secret)
    canal.authenticate(peer_address="::1", secret=secret)

    for adresse in ("192.168.1.50", "10.0.0.1", "8.8.8.8"):
        with pytest.raises(ChannelRefused):
            canal.authenticate(peer_address=adresse, secret=secret)

    with pytest.raises(ChannelRefused):
        canal.authenticate(peer_address="127.0.0.1", secret="")
    with pytest.raises(ChannelRefused):
        canal.authenticate(peer_address="127.0.0.1", secret="mauvais-secret")
    with pytest.raises(ChannelRefused):
        canal.authenticate(peer_address="::1", secret=None)


def test_le_refus_est_explicite_et_nomme_jamais_un_booleen_ni_none():
    """Le refus lève ChannelRefused ; ce n'est ni un booléen muet ni None."""
    from src.hostagent.channel import ChannelRefused, LocalChannel

    assert issubclass(ChannelRefused, Exception)
    assert type(ChannelRefused) is type

    canal = LocalChannel(secret="partage-installation")
    with pytest.raises(ChannelRefused) as captured:
        canal.authenticate(peer_address="192.168.1.50", secret="partage-installation")
    assert type(captured.value) is ChannelRefused
    assert captured.value is not None
    assert captured.value is not False
    assert not isinstance(captured.value, bool)


def test_la_comparaison_du_secret_utilise_compare_digest():
    """La comparaison du secret passe par hmac.compare_digest, pas par ==."""
    import inspect

    from src.hostagent import channel

    source = inspect.getsource(channel)
    assert "compare_digest" in source
    assert "hmac" in source


def test_le_canal_ne_transporte_que_les_primitives_du_contrat():
    """Un nom hors PRIMITIVES, y compris shell, est refusé ; le canal réutilise is_permitted."""
    import inspect

    from src.hostagent import channel
    from src.hostagent.channel import ChannelRefused, LocalChannel
    from src.hostagent.contract import PRIMITIVES, is_permitted

    source = inspect.getsource(channel)
    assert "is_permitted" in source

    secret = "partage-installation"
    canal = LocalChannel(secret=secret)
    canal.authenticate(peer_address="127.0.0.1", secret=secret)

    for nom in PRIMITIVES:
        assert is_permitted(nom) is True
        canal.handle({"primitive": nom})

    for nom in ("shell", "exec", "spawn", "file.read", "hors.contrat"):
        assert is_permitted(nom) is False
        with pytest.raises(ChannelRefused):
            canal.handle({"primitive": nom})


def test_un_message_malforme_est_refuse_proprement():
    """Pas un dict, primitive absente ou JSON invalide : erreur nommée, pas de KeyError ni TypeError nu."""
    from src.hostagent.channel import ChannelRefused, LocalChannel

    secret = "partage-installation"
    canal = LocalChannel(secret=secret)
    canal.authenticate(peer_address="127.0.0.1", secret=secret)

    malformes = (
        ["audio.capture"],
        None,
        42,
        {},
        {"args": []},
        "{",
        "pas du json",
    )
    for message in malformes:
        with pytest.raises(ChannelRefused) as captured:
            canal.handle(message)
        assert type(captured.value) is ChannelRefused
        assert not isinstance(captured.value, KeyError)
        assert not isinstance(captured.value, TypeError)


def test_toute_invocation_acceptee_est_journalisee():
    """Chaque invocation acceptée est enregistrée dans le journal injecté (miroir ADR-016)."""
    from src.hostagent.channel import ChannelRefused, LocalChannel

    journal = []
    secret = "partage-installation"
    canal = LocalChannel(secret=secret, journal=journal)
    canal.authenticate(peer_address="127.0.0.1", secret=secret)

    canal.handle({"primitive": "audio.capture"})
    canal.handle({"primitive": "audio.render"})
    canal.handle({"primitive": "input.inject"})
    canal.handle('{"primitive": "surface.draw"}')
    with pytest.raises(ChannelRefused):
        canal.handle({"primitive": "shell"})

    assert journal == [
        "audio.capture",
        "audio.render",
        "input.inject",
        "surface.draw",
    ]
