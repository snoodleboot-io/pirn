"""Restricted ``ast``-based arithmetic evaluator (zero third-party deps).

:func:`evaluate_expression` parses an expression into an AST and walks it with a
strict node whitelist, so it evaluates ordinary arithmetic *without* ever calling
``eval``/``exec`` and without exposing attribute access, subscripting, names, or
arbitrary calls. Every construct that could reach the host — ``__import__``,
attribute traversal (``().__class__``), comprehensions, lambdas, f-strings — is
rejected before any value is produced.

Supported:
    * numeric literals (``int``/``float``/``complex`` are rejected → real only)
    * unary ``+``/``-``
    * binary ``+ - * / // % **``
    * a small whitelist of pure functions (``abs round min max sqrt floor ceil``)
    * a small whitelist of constants (``pi e tau``)

A hard cap on exponent magnitude blocks pathological ``**`` blow-ups (e.g.
``9**9**9``) that would otherwise burn CPU/memory.
"""

from __future__ import annotations

import ast
import math
from collections.abc import Callable
from typing import Any


def evaluate_expression(expression: str) -> float:
    """Safely evaluate an arithmetic ``expression`` and return a real number.

    Args:
        expression: The arithmetic expression to evaluate (e.g. ``"2 + 3 * 4"``).

    Returns:
        The numeric result as an ``int`` or ``float`` (both are ``float``-typed
        for the caller; ``int`` results are preserved as ``int`` values).

    Raises:
        TypeError: If ``expression`` is not a string.
        ValueError: If ``expression`` is empty, is not parseable, contains a
            disallowed construct (names, calls to non-whitelisted functions,
            attribute access, imports, …), or overflows the exponent guard.
        ZeroDivisionError: If the expression divides by zero.
    """
    if not isinstance(expression, str):
        raise TypeError(f"calculator: expression must be a string, got {type(expression).__name__}")
    if not expression.strip():
        raise ValueError("calculator: expression must be a non-empty string")
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ValueError(
            f"calculator: could not parse expression {expression!r}: {exc.msg}"
        ) from exc
    return _eval_node(tree.body)


def _eval_node(node: ast.AST) -> Any:
    """Recursively evaluate a whitelisted AST node, rejecting anything else."""
    binary_ops = _binary_operators()
    unary_ops = _unary_operators()

    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise ValueError(f"calculator: unsupported literal {node.value!r}")
        return node.value
    if isinstance(node, ast.UnaryOp):
        handler = unary_ops.get(type(node.op))
        if handler is None:
            raise ValueError(f"calculator: unsupported unary operator {type(node.op).__name__}")
        return handler(_eval_node(node.operand))
    if isinstance(node, ast.BinOp):
        handler = binary_ops.get(type(node.op))
        if handler is None:
            raise ValueError(f"calculator: unsupported operator {type(node.op).__name__}")
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        if isinstance(node.op, ast.Pow):
            _guard_power(right)
        return handler(left, right)
    if isinstance(node, ast.Name):
        constants = _named_constants()
        if node.id in constants:
            return constants[node.id]
        raise ValueError(f"calculator: unknown name {node.id!r}")
    if isinstance(node, ast.Call):
        return _eval_call(node)
    raise ValueError(f"calculator: unsupported expression element {type(node).__name__}")


def _eval_call(node: ast.Call) -> Any:
    """Evaluate a call to a whitelisted, argument-only function."""
    if node.keywords:
        raise ValueError("calculator: keyword arguments are not allowed")
    if not isinstance(node.func, ast.Name):
        raise ValueError("calculator: only direct calls to whitelisted functions are allowed")
    functions = _allowed_functions()
    func = functions.get(node.func.id)
    if func is None:
        raise ValueError(f"calculator: function {node.func.id!r} is not allowed")
    args = [_eval_node(arg) for arg in node.args]
    return func(*args)


def _guard_power(exponent: float) -> None:
    """Reject exponents large enough to cause a runaway ``**`` computation."""
    if abs(exponent) > 1000:
        raise ValueError("calculator: exponent too large (magnitude > 1000)")


def _binary_operators() -> dict[type[ast.operator], Callable[[Any, Any], Any]]:
    """Map binary AST operator types to their pure numeric implementations."""
    import operator

    return {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
    }


def _unary_operators() -> dict[type[ast.unaryop], Callable[[Any], Any]]:
    """Map unary AST operator types to their pure numeric implementations."""
    import operator

    return {ast.UAdd: operator.pos, ast.USub: operator.neg}


def _named_constants() -> dict[str, float]:
    """Return the whitelist of allowed named mathematical constants."""
    return {"pi": math.pi, "e": math.e, "tau": math.tau}


def _allowed_functions() -> dict[str, Callable[..., Any]]:
    """Return the whitelist of allowed pure numeric functions."""
    return {
        "abs": abs,
        "round": round,
        "min": min,
        "max": max,
        "sqrt": math.sqrt,
        "floor": math.floor,
        "ceil": math.ceil,
    }
