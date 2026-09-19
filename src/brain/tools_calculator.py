"""Outil local et deterministe de calcul arithmetique.

Le texte vient d'un modele, donc il est traite comme une expression hostile :
aucun ``eval`` n'est utilise. L'AST est limite a des nombres et aux operateurs
arithmetiques autorises, puis les operations sont faites avec ``Decimal`` pour
que les decimales francaises restent reproductibles.
"""
from __future__ import annotations

import ast
import operator
from decimal import Decimal, InvalidOperation, localcontext
from typing import Any

from src.brain.tools import ToolRegistry, ToolSpec

CALCULATOR_NAME = "calculer"
CALCULATOR_DESCRIPTION = (
    "Calcule une expression arithmetique deterministe, avec les operations +, "
    "-, *, /, %, // et les parentheses. Utilise-le pour verifier un calcul "
    "numerique plutot que de le faire mentalement."
)
CALCULATOR_PARAMETERS = {
    "type": "object",
    "properties": {
        "expression": {
            "type": "string",
            "description": "Expression arithmetique, par exemple 8376 / 2,8.",
        }
    },
    "required": ["expression"],
    "additionalProperties": False,
}

_ERROR_MESSAGE = "Je ne peux pas calculer cette expression."
_MAX_EXPRESSION_CHARS = 240
_MAX_AST_NODES = 80
_MAX_RESULT_CHARS = 200
_DECIMAL_PRECISION = 28


class CalculatorError(ValueError):
    """Expression absente, interdite ou impossible a calculer."""


_BINARY_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv,
}
_UNARY_OPERATORS = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def evaluate_expression(expression: str) -> str:
    """Evalue une expression autorisee et rend un nombre lisible.

    Les erreurs sont exposees sous forme de ``CalculatorError`` pour permettre
    a l'adaptateur d'outil de rendre une phrase fixe, sans divulguer un detail
    d'implementation au modele ou a la voix.
    """
    if not isinstance(expression, str) or not expression.strip():
        raise CalculatorError("expression vide")
    if len(expression) > _MAX_EXPRESSION_CHARS:
        raise CalculatorError("expression trop longue")

    # La virgule est le separateur decimal attendu par la voix francaise. Une
    # virgule de tuple devient un point puis echoue naturellement au parsing.
    source = expression.replace(",", ".").strip()
    try:
        tree = ast.parse(source, mode="eval")
    except (SyntaxError, ValueError, TypeError) as exc:
        raise CalculatorError("syntaxe invalide") from exc

    nodes = list(ast.walk(tree))
    if len(nodes) > _MAX_AST_NODES:
        raise CalculatorError("expression trop complexe")

    with localcontext() as context:
        context.prec = _DECIMAL_PRECISION
        try:
            value = _evaluate_node(tree.body)
        except CalculatorError:
            raise
        except (ArithmeticError, InvalidOperation, ValueError, TypeError) as exc:
            raise CalculatorError("operation impossible") from exc

    if not value.is_finite():
        raise CalculatorError("resultat non fini")
    rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    if rendered in {"", "-0"}:
        rendered = "0"
    if len(rendered) > _MAX_RESULT_CHARS:
        raise CalculatorError("resultat trop grand")
    return rendered


def _evaluate_node(node: ast.AST) -> Decimal:
    if isinstance(node, ast.Constant):
        # bool est une sous-classe de int, mais n'est pas un nombre saisi.
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise CalculatorError("constante interdite")
        try:
            value = Decimal(str(node.value))
        except (InvalidOperation, ValueError) as exc:
            raise CalculatorError("nombre invalide") from exc
        if not value.is_finite():
            raise CalculatorError("nombre non fini")
        return value

    if isinstance(node, ast.UnaryOp):
        operation = _UNARY_OPERATORS.get(type(node.op))
        if operation is None:
            raise CalculatorError("operateur unaire interdit")
        return operation(_evaluate_node(node.operand))

    if isinstance(node, ast.BinOp):
        left = _evaluate_node(node.left)
        right = _evaluate_node(node.right)
        if isinstance(node.op, ast.Pow):
            # La puissance est utile mais bornee pour eviter un calcul ou une
            # sortie disproportionnee provoquee par un modele mal forme.
            if right != right.to_integral_value() or abs(right) > 100:
                raise CalculatorError("puissance interdite")
            try:
                return left**int(right)
            except (ArithmeticError, InvalidOperation, ValueError) as exc:
                raise CalculatorError("puissance impossible") from exc

        operation = _BINARY_OPERATORS.get(type(node.op))
        if operation is None:
            raise CalculatorError("operateur interdit")
        try:
            return operation(left, right)
        except ZeroDivisionError as exc:
            raise CalculatorError("division par zero") from exc
        except (ArithmeticError, InvalidOperation, ValueError, ZeroDivisionError) as exc:
            raise CalculatorError("operation impossible") from exc

    # Aucun nom, appel, attribut, index, comprehension ou mot-clef n'est
    # executable : seuls les noeuds ci-dessus appartiennent au langage.
    raise CalculatorError("expression interdite")


class Calculator:
    """Handler async conforme au contrat ``ToolSpec``."""

    async def __call__(self, expression: str) -> str:
        try:
            return evaluate_expression(expression)
        except CalculatorError:
            return _ERROR_MESSAGE


# Nom francais utile aux imports de composants qui parlent de la calculatrice.
Calculatrice = Calculator


def register_calculator(registry: ToolRegistry) -> ToolSpec:
    """Expose ``calculer`` dans le registre, sans configuration externe."""
    return registry.register(
        ToolSpec(
            name=CALCULATOR_NAME,
            description=CALCULATOR_DESCRIPTION,
            parameters=CALCULATOR_PARAMETERS,
            danger="read",
            handler=Calculator(),
        )
    )


register_calculer = register_calculator
