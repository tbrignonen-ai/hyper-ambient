"""
Tests du bus d'événements et de son horloge monotone.
"""
import time


def test_events_are_delivered_in_emission_order_with_monotonic_stamps():
    """Trois producteurs, 100 événements : livrés dans l'ordre d'émission, stamps strictement croissants."""
    from src.core.bus.event_bus import EventBus

    bus = EventBus()
    recus = []
    bus.subscribe(recus.append)

    emis = []

    def producteur(identifiant):
        def publier(seq):
            return bus.publish({"producteur": identifiant, "seq": seq})

        return publier

    producteurs = (producteur(0), producteur(1), producteur(2))
    for i in range(100):
        emis.append(producteurs[i % 3](i))

    assert len(recus) == 100
    assert all(recu is emi for recu, emi in zip(recus, emis))
    stamps = [evenement.stamp for evenement in recus]
    assert all(stamps[i] < stamps[i + 1] for i in range(len(stamps) - 1))


def test_le_bus_sans_abonne_ne_leve_pas_et_conserve_la_publication():
    """Sans abonné, publish ne lève pas et retourne l'événement publié."""
    from src.core.bus.event_bus import EventBus

    bus = EventBus()
    evenement = bus.publish({"orphelin": True})
    assert evenement.payload == {"orphelin": True}
    assert isinstance(evenement.stamp, float)


def test_plusieurs_abonnes_recoivent_le_meme_evenement_dans_l_ordre_d_abonnement():
    """Chaque abonné reçoit le même événement, dans l'ordre d'abonnement."""
    from src.core.bus.event_bus import EventBus

    bus = EventBus()
    ordre = []
    recus = []

    def abonne(nom):
        def handler(event):
            ordre.append(nom)
            recus.append(event)

        return handler

    bus.subscribe(abonne("premier"))
    bus.subscribe(abonne("deuxieme"))
    bus.subscribe(abonne("troisieme"))
    publie = bus.publish({"partage": True})

    assert ordre == ["premier", "deuxieme", "troisieme"]
    assert recus == [publie, publie, publie]
    assert recus[0] is recus[1] is recus[2] is publie


def test_l_horodatage_vient_d_une_horloge_monotone_et_non_murale():
    """Les stamps sont cohérents avec time.monotonic, pas avec l'heure murale POSIX."""
    from src.core.bus.event_bus import EventBus

    bus = EventBus()
    monotone_avant = time.monotonic()
    posix_avant = time.time()
    premier = bus.publish("alpha")
    second = bus.publish("omega")
    monotone_apres = time.monotonic()
    posix_apres = time.time()

    assert premier.stamp < second.stamp
    assert monotone_avant <= premier.stamp <= monotone_apres
    assert monotone_avant <= second.stamp <= monotone_apres
    assert not (posix_avant <= premier.stamp <= posix_apres)
    assert not (posix_avant <= second.stamp <= posix_apres)


def test_une_exception_d_un_abonne_n_empeche_pas_les_autres_de_recevoir():
    """Une exception levée par un abonné n'empêche pas les autres de recevoir l'événement."""
    from src.core.bus.event_bus import EventBus

    bus = EventBus()
    recus = []

    def abonne_fragile(event):
        recus.append("fragile")
        raise RuntimeError("echec volontaire")

    def abonne_robuste(event):
        recus.append("robuste")
        recus.append(event)

    bus.subscribe(abonne_fragile)
    bus.subscribe(abonne_robuste)
    try:
        bus.publish({"survecu": True})
    except RuntimeError:
        pass

    assert recus[0] == "fragile"
    assert recus[1] == "robuste"
    assert recus[2].payload == {"survecu": True}
