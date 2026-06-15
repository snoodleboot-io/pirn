"""``DerivedColumnCalculator`` — evaluate safe expressions to produce new columns.

Expressions are parsed with :mod:`ast` and evaluated against each row's
values using a restricted evaluator that supports:

* Arithmetic operators: ``+``, ``-``, ``*``, ``/``, ``//``, ``%``, ``**``
* Unary operators: ``-``, ``+``
* Comparisons: ``==``, ``!=``, ``<``, ``<=``, ``>``, ``>=``
* Boolean operators: ``and``, ``or``, ``not``
* Column references by name (resolved from the current row dict)
* Numeric and string literals

``eval()`` is never called; the AST is walked node-by-node.

Algorithm:
    1. Receive resolved ``rows`` and ``expressions`` in ``process()``.
    2. Validate each expression spec: non-empty ``column`` identifier and
       non-empty, parseable ``expression`` string.
    3. For each row evaluate each expression AST against the current row
       dict, appending new columns in declaration order (so later
       expressions can reference earlier ones).
    4. Return the enriched row list.

References:
    [1] pirn — IdentifierValidator (SQL injection guard):
        pirn_data/identifier_validator.py
"""

from __future__ import annotations

import ast
import operator
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_data.identifier_validator import IdentifierValidator


class DerivedColumnCalculator(Knot):
    """Append computed columns to each row using safe AST-evaluated expressions."""

    _bin_ops: ClassVar[dict[type, Any]] = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
    }
    _cmp_ops: ClassVar[dict[type, Any]] = {
        ast.Eq: operator.eq,
        ast.NotEq: operator.ne,
        ast.Lt: operator.lt,
        ast.LtE: operator.le,
        ast.Gt: operator.gt,
        ast.GtE: operator.ge,
    }
    _unary_ops: ClassVar[dict[type, Any]] = {
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }

    def __init__(
        self,
        *,
        rows: Knot | list,
        expressions: Knot | list,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            rows=rows,
            expressions=expressions,
            _config=_config,
            **kwargs,
        )

    @classmethod
    def _eval_node(cls, node: ast.AST, row: dict[str, Any]) -> Any:
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            if node.id not in row:
                raise ValueError(f"DerivedColumnCalculator: unknown column {node.id!r}")
            return row[node.id]
        if isinstance(node, ast.BinOp):
            op = cls._bin_ops.get(type(node.op))
            if op is None:
                raise ValueError(
                    f"DerivedColumnCalculator: unsupported operator {type(node.op).__name__}"
                )
            return op(cls._eval_node(node.left, row), cls._eval_node(node.right, row))
        if isinstance(node, ast.UnaryOp):
            op = cls._unary_ops.get(type(node.op))
            if op is None:
                raise ValueError(
                    f"DerivedColumnCalculator: unsupported unary operator {type(node.op).__name__}"
                )
            return op(cls._eval_node(node.operand, row))
        if isinstance(node, ast.Compare):
            left = cls._eval_node(node.left, row)
            for cmp_op, comparator in zip(node.ops, node.comparators, strict=False):
                op = cls._cmp_ops.get(type(cmp_op))
                if op is None:
                    raise ValueError(
                        f"DerivedColumnCalculator: unsupported comparison {type(cmp_op).__name__}"
                    )
                right = cls._eval_node(comparator, row)
                if not op(left, right):
                    return False
                left = right
            return True
        if isinstance(node, ast.BoolOp):
            if isinstance(node.op, ast.And):
                return all(cls._eval_node(v, row) for v in node.values)
            return any(cls._eval_node(v, row) for v in node.values)
        if isinstance(node, ast.Expression):
            return cls._eval_node(node.body, row)
        raise ValueError(
            f"DerivedColumnCalculator: unsupported expression node {type(node).__name__}"
        )

    async def process(
        self,
        *,
        rows: Any,
        expressions: Any,
        **_: Any,
    ) -> list[dict[str, Any]]:
        compiled: list[tuple[str, ast.Expression]] = []
        for spec in expressions:
            if "column" not in spec:
                raise ValueError("DerivedColumnCalculator: spec missing required field 'column'")
            col = spec["column"]
            IdentifierValidator.validate_column("expressions[column]", col)
            if "expression" not in spec:
                raise ValueError(
                    "DerivedColumnCalculator: spec missing required field 'expression'"
                )
            expr_str = spec["expression"]
            if not isinstance(expr_str, str) or not expr_str:
                raise ValueError("DerivedColumnCalculator: expression must be a non-empty string")
            try:
                tree = ast.parse(expr_str, mode="eval")
            except SyntaxError as exc:
                raise ValueError(
                    f"DerivedColumnCalculator: invalid expression {expr_str!r}: {exc}"
                ) from exc
            compiled.append((col, tree))
        result: list[dict[str, Any]] = []
        for row in rows:
            new_row = dict(row)
            for col, tree in compiled:
                new_row[col] = self._eval_node(tree, new_row)
            result.append(new_row)
        return result
