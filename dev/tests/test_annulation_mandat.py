"""Annuler une demande confiée à un harnais (séance du 24 sept).

« Annule la demande à Codex. » repartait chez Codex comme une nouvelle
question, deux fois, et elle répondait « Que veux-tu que je demande à
Codex ? ». L'annulation est une décision locale, prise avant le cerveau.
"""
import asyncio
import time

from src.brain.mandat import Mandat, RegistreMandats, annuler_mandats


def _mandat(identifiant, harnais="Codex", etat="en_cours"):
    return Mandat(
        identifiant=identifiant,
        harnais=harnais,
        question="q",
        sujet="s",
        depose_a=time.monotonic(),
        etat=etat,
    )


def test_annule_la_demande_en_cours_et_le_dit():
    async def scenario():
        registre = RegistreMandats()
        mandat = _mandat("m1")
        mandat.tache = asyncio.create_task(asyncio.sleep(60))
        registre.deposer(mandat)
        phrase = annuler_mandats(registre, "Annule la demande à Codex.")
        await asyncio.sleep(0)
        return registre, mandat, phrase

    registre, mandat, phrase = asyncio.run(scenario())
    assert phrase == "J'ai annulé la demande à Codex."
    assert registre.en_cours() == []
    assert mandat.tache.cancelled()


def test_rien_en_cours_le_dit_sans_rien_envoyer():
    registre = RegistreMandats()
    registre.deposer(_mandat("m1", etat="fini"))
    registre.marquer_annonce("m1")
    assert annuler_mandats(registre, "Annule la demande à Codex.") == (
        "Il n'y a aucune demande en cours à annuler."
    )


def test_ne_touche_que_le_harnais_nomme():
    registre = RegistreMandats()
    registre.deposer(_mandat("c", harnais="Codex"))
    registre.deposer(_mandat("k", harnais="Claude"))
    assert annuler_mandats(registre, "laisse tomber Claude") == (
        "J'ai annulé la demande à Claude."
    )
    assert [m.harnais for m in registre.en_cours()] == ["Codex"]


def test_une_vraie_demande_n_est_pas_une_annulation():
    registre = RegistreMandats()
    for phrase in (
        "Demande à Codex de compter les répertoires.",
        "Demande à Codex comment annuler un commit git dans ce dépôt.",
        "Quelle heure est-il ?",
    ):
        assert annuler_mandats(registre, phrase) is None, phrase


def test_le_tour_vocal_annule_avant_le_cerveau():
    import inspect

    from dev.scripts import serve_hostagent

    source = inspect.getsource(serve_hostagent.HostPipeline._enchainer)
    assert source.index("annuler_mandats(self._mandats, prompt)") < source.index(
        "self._memoire.doit_fermer("
    )
