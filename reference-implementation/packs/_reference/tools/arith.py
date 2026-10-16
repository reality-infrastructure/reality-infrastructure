"""A deterministic arithmetic evaluator exposed as a pack tool.

Parses with ``ast``; only + - * / and parentheses over numeric literals are
accepted.  No names, no calls, no eval.  Results are exact Decimals.
"""

from __future__ import annotations

import ast
from decimal import Decimal, DivisionByZero, InvalidOperation

from engine.errors import ToolError
from engine.tools import tool

_BIN = {ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b,
        ast.Mult: lambda a, b: a * b, ast.Div: lambda a, b: a / b}


def evaluate(expression: str) -> Decimal:
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as e:
        raise ToolError(f"bad expression {expression!r}: {e.msg}") from e

    def ev(node) -> Decimal:
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return Decimal(str(node.value))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -ev(node.operand)
        if isinstance(node, ast.BinOp) and type(node.op) in _BIN:
            try:
                return _BIN[type(node.op)](ev(node.left), ev(node.right))
            except (DivisionByZero, InvalidOperation) as e:
                raise ToolError(f"bad expression {expression!r}: {e}") from e
        raise ToolError(f"bad expression {expression!r}: unsupported syntax {type(node).__name__}")

    value = ev(tree)
    return value.quantize(Decimal(1)) if value == value.to_integral_value() else value.normalize()


@tool(
    id="_reference.arith.eval",
    effect="read",
    deterministic=True,
    description="Evaluate an arithmetic expression (+ - * / and parentheses) exactly. Returns the canonical decimal string.",
    input_schema={"type": "object", "additionalProperties": False, "required": ["expression"],
                  "properties": {"expression": {"type": "string", "minLength": 1}}},
)
def arith_eval(args: dict, ctx) -> dict:
    return {"expression": args["expression"], "value": str(evaluate(args["expression"]))}
