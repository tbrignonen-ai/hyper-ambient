"""Tests TDD de l'outil arithmetique local ``calculer``."""

import asyncio

import pytest

from src.brain.tools import ToolRegistry
from src.brain.tools_calculator import (
    CALCULATOR_PARAMETERS,
    Calculator,
    CalculatorError,
    evaluate_expression,
    register_calculator,
)
from src.brain.tools_web import register_web_search


def test_evalue_arithmetique_avec_priorite_et_parentheses():
    assert evaluate_expression("2 + 3 * (4 - 1)") == "11"


def test_accepte_la_virgule_decimale_francaise():
    assert evaluate_expression("8376 / 2,8") == "2991.428571428571428571428571"


def test_n_execute_ni_nom_ni_appel_ni_attribut():
    for expression in ("__import__('os')", "open('secret')", "(1).__class__"):
        with pytest.raises(CalculatorError):
            evaluate_expression(expression)


def test_refuse_division_par_zero():
    with pytest.raises(CalculatorError, match="zero"):
        evaluate_expression("1 / 0")


def test_handler_rend_une_erreur_parlable_sans_exception():
    resultat = asyncio.run(Calculator()("1 / 0"))
    assert resultat == "Je ne peux pas calculer cette expression."


def test_enregistrement_deterministe_et_compatible_avec_web_search():
    registry = ToolRegistry()
    register_web_search(registry, api_key="", client=object())
    spec = register_calculator(registry)

    assert spec.name == "calculer"
    assert registry.danger_of("calculer") == "read"
    assert registry.get("calculer").parameters == CALCULATOR_PARAMETERS
    assert [schema["function"]["name"] for schema in registry.schemas()] == [
        "web_search",
        "calculer",
    ]

