"""``IbisJoin`` — Tier-3 binary join that extends the deferred expression
with ``ibis.Table.join(...)``.

Two ways to express the join condition:

1. ``predicates=("user_id",)`` — column name(s) common to both sides.
2. ``predicates=lambda left, right: left.user_id == right.customer_id``
   — caller-supplied predicate function returning an ``ibis.Expr``.

``how`` matches Ibis's vocabulary: ``inner`` / ``left`` / ``right`` /
``outer`` / ``semi`` / ``anti`` / ``cross``.

Algorithm:
    1. Validate that ``how`` is one of the allowed join types.
    2. If ``how == "cross"``: validate no predicates are supplied, then call
       ``left.cross_join(right)`` and return the extended expression.
    3. Otherwise: validate that ``predicates`` is supplied.
    4. If ``predicates`` is callable: invoke it with ``(left_expr, right_expr)``
       to obtain an ``ibis.Expr`` condition.
    5. If ``predicates`` is a string or sequence of strings: validate each is
       a non-empty string.
    6. Call ``left.join(right, predicates=..., how=how)`` to extend the
       deferred expression.
    7. Return a new ``IbisTable`` wrapping the joined expression.

    No rows are read from the backend — the join becomes a SQL ``JOIN``
    clause when compiled and executed.

    ```text
    if how == "cross":
        out = left.cross_join(right)
    elif callable(predicates):
        condition = predicates(left, right)
        out = left.join(right, predicates=condition, how=how)
    else:
        out = left.join(right, predicates=predicates, how=how)
    return IbisTable(out)
    ```

References:
    [1] Ibis — Table.join:
        https://ibis-project.org/reference/expression-tables.html#ibis.expr.types.relations.Table.join
    [2] Ibis — Table.cross_join:
        https://ibis-project.org/reference/expression-tables.html#ibis.expr.types.relations.Table.cross_join
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

import ibis

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.lazy.ibis.ibis_table import IbisTable


class IbisJoin(Knot):
    """Binary join over two :class:`IbisTable` parents."""

    _allowed_how: tuple[str, ...] = (
        "inner", "left", "right", "outer", "semi", "anti", "cross",
    )

    def __init__(
        self,
        *,
        left: Knot,
        right: Knot,
        predicates: (
            Knot | str | Sequence[str] | Callable[[ibis.Table, ibis.Table], Any] | None
        ) = None,
        how: Knot | str = "inner",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            left=left,
            right=right,
            predicates=predicates,
            how=how,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        left: IbisTable,
        right: IbisTable,
        predicates: Any,
        how: Any,
        **_: Any,
    ) -> IbisTable:
        """Join the left and right Ibis expressions on the configured predicates.

        Args:
            left: The left-side IbisTable.
            right: The right-side IbisTable to join against.
            predicates: Column name(s) or callable (left, right) -> ibis.Expr, or None for cross.
            how: Join type string.

        Returns:
            A new IbisTable containing the joined deferred expression.
        """
        if how not in self._allowed_how:
            raise ValueError(
                f"IbisJoin: how must be one of {list(self._allowed_how)}, got {how!r}"
            )
        if how == "cross":
            if predicates is not None:
                raise TypeError(
                    "IbisJoin: cross join takes no predicates"
                )
            joined = left.expression.cross_join(right.expression)
            return left.with_expression(joined)
        if predicates is None:
            raise TypeError(
                "IbisJoin: predicates is required for non-cross joins"
            )
        if isinstance(predicates, Sequence) and not isinstance(predicates, str):
            for column in predicates:
                if not isinstance(column, str) or not column:
                    raise TypeError(
                        "IbisJoin: predicates sequence must be non-empty strings"
                    )
        if callable(predicates):
            condition = predicates(left.expression, right.expression)
            joined = left.expression.join(
                right.expression, predicates=condition, how=how,
            )
        elif isinstance(predicates, str):
            joined = left.expression.join(
                right.expression, predicates=predicates, how=how,
            )
        else:
            joined = left.expression.join(
                right.expression,
                predicates=list(predicates),
                how=how,
            )
        return left.with_expression(joined)
