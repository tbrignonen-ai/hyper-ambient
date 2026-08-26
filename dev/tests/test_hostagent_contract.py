"""
Tests du contrat du host-agent (ADR-016) : quatre primitives, zéro exécution.
"""
import pytest


def test_contract_exposes_exactly_four_primitives_and_no_exec():
    """Exactement quatre primitives, ces noms-là, et aucun nom d'exécution n'est permis."""
    from src.hostagent.contract import PRIMITIVES, is_permitted

    attendues = {
        "audio.capture",
        "audio.render",
        "input.inject",
        "surface.draw",
    }
    assert len(PRIMITIVES) == 4
    assert set(PRIMITIVES) == attendues
    for nom in attendues:
        assert is_permitted(nom) is True

    assert is_permitted("shell") is False
    assert is_permitted("exec") is False
    assert is_permitted("spawn") is False
    assert is_permitted("file.read") is False
    assert is_permitted("file.write") is False
    assert is_permitted("subprocess") is False
    assert is_permitted("eval") is False
    assert is_permitted("audio.play") is False
    assert is_permitted("") is False


def test_input_inject_porte_un_evenement_unitaire_et_refuse_une_sequence():
    """input.inject accepte un seul événement et refuse une liste ou plusieurs événements."""
    from src.hostagent.contract import HostAgentContract, SequenceNotAllowedError

    contrat = HostAgentContract(journal=[])
    evenement = {"kind": "key", "code": "KeyA"}
    contrat.invoke("input.inject", evenement)

    with pytest.raises(SequenceNotAllowedError):
        contrat.invoke("input.inject", [evenement])
    with pytest.raises(SequenceNotAllowedError):
        contrat.invoke("input.inject", [evenement, evenement])
    with pytest.raises(SequenceNotAllowedError):
        contrat.invoke("input.inject", evenement, evenement)


def test_le_contrat_ne_porte_aucune_notion_de_decision():
    """Aucun nom public du module n'évoque une liste blanche, un mode, une permission ou un locuteur."""
    from src.hostagent import contract

    racines_interdites = (
        "allow",
        "whitelist",
        "permission",
        "mode",
        "speaker",
        "gate",
        "authorize",
    )
    publics = [nom for nom in dir(contract) if not nom.startswith("_")]
    for nom in publics:
        minuscule = nom.lower()
        for racine in racines_interdites:
            assert racine not in minuscule, (
                f"nom public {nom!r} évoque une décision ({racine})"
            )


def test_toute_primitive_appelee_est_journalisee():
    """Un contrat instancié avec un journal injecté enregistre le nom à chaque invocation."""
    from src.hostagent.contract import HostAgentContract

    journal = []
    contrat = HostAgentContract(journal=journal)
    contrat.invoke("audio.capture", {"rate": 16000})
    contrat.invoke("audio.render", [])
    contrat.invoke("input.inject", {"kind": "mouse", "button": "left"})
    contrat.invoke("surface.draw", {"width": 1, "height": 1})
    assert journal == [
        "audio.capture",
        "audio.render",
        "input.inject",
        "surface.draw",
    ]


def test_une_primitive_inconnue_leve_une_erreur_nommee():
    """Une primitive inconnue lève UnknownPrimitiveError, jamais un KeyError nu."""
    from src.hostagent.contract import HostAgentContract, UnknownPrimitiveError

    contrat = HostAgentContract(journal=[])
    with pytest.raises(UnknownPrimitiveError) as captured:
        contrat.invoke("shell")
    assert type(captured.value) is UnknownPrimitiveError
    assert not isinstance(captured.value, KeyError)
    assert "shell" in str(captured.value)
