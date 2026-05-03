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
"""

from __future__ import annotations

import ast
import operator
from typing import Any, Sequence

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.identifier_validator import IdentifierValidator

class DerivedColumnCalculator(Knot):
    """Append computed columns to each row using safe AST-evaluated expressions."""

    def __init__(
        self,
        *,
        rows: Knot,
        expressions: Sequence[dict[str, str]],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        """Initialise the calculator.

        Args:
            rows:        Upstream rows knot.
            expressions: List of dicts, each with ``column`` (output name) and
                         ``expression`` (safe expression string).
        """
        compiled: list[tuple[str, ast.Expression]] = []
        for spec in expressions:
            col = spec.get("column", "")
            IdentifierValidator.validate_column("expressions[column]", col)
            expr_str = spec.get("expression", "")
            if not isinstance(expr_str, str) or not expr_str:
                raise ValueError(
                    "DerivedColumnCalculator: expression must be a non-empty string"
                )
            try:
                tree = ast.parse(expr_str, mode="eval")
            except SyntaxError as exc:
                raise ValueError(
                    f"DerivedColumnCalculator: invalid expression {expr_str!r}: {exc}"
                ) from exc
            compiled.append((col, tree))
        self._compiled = compiled
        super().__init__(rows=rows, _config=_config, **kwargs)

    _bin_ops: dict[type, Any] = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
    }
    _cmp_ops: dict[type, Any] = {
        ast.Eq: operator.eq,
        ast.NotEq: operator.ne,
        ast.Lt: operator.lt,
        ast.LtE: operator.le,
        ast.Gt: operator.gt,
        ast.GtE: operator.ge,
    }
    _unary_ops: dict[type, Any] = {
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }

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
                    f"DerivedColumnCalculator: unsupported unary operator "
                    f"{type(node.op).__name__}"
                )
            return op(cls._eval_node(node.operand, row))
        if isinstance(node, ast.Compare):
            left = cls._eval_node(node.left, row)
            for cmp_op, comparator in zip(node.ops, node.comparators):
                op = cls._cmp_ops.get(type(cmp_op))
                if op is None:
                    raise ValueError(
                        f"DerivedColumnCalculator: unsupported comparison "
                        f"{type(cmp_op).__name__}"
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
            f"DerivedColumnCalculator: unsupported expression node "
            f"{type(node).__name__}"
        )

    async def process(
        self, rows: list[dict[str, Any]], **_: Any
    ) -> list[dict[str, Any]]:
        """Evaluate each expression against each row and append the result columns.

        Args:
            rows: Upstream rows as a list of dicts.

        Returns:
            Rows with new derived columns appended.
        """
        result: list[dict[str, Any]] = []
        for row in rows:
            new_row = dict(row)
            for col, tree in self._compiled:
                new_row[col] = self._eval_node(tree, new_row)
            result.append(new_row)
        return result
