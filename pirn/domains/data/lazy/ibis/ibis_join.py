"""``IbisJoin`` — Tier-3 binary join that extends the deferred expression
with ``ibis.Table.join(...)``.
"""

from __future__ import annotations

from typing import Any, Callable, Sequence

import ibis

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.lazy.ibis.ibis_table import IbisTable


class IbisJoin(Knot):
    """Binary join over two :class:`IbisTable` parents.

    Two ways to express the join condition:

    1. ``predicates=("user_id",)`` — column name(s) common to both sides.
    2. ``predicates=lambda left, right: left.user_id == right.customer_id``
       — caller-supplied predicate function returning an ``ibis.Expr``.

    ``how`` matches Ibis's vocabulary: ``inner`` / ``left`` / ``right`` /
    ``outer`` / ``semi`` / ``anti`` / ``cross``.
    """

    def __init__(
        self,
        *,
        left: Knot,
        right: Knot,
        predicates: str | Sequence[str] | Callable[[ibis.Table, ibis.Table], Any] | None = None,
        how: str = "inner",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        allowed_how = ("inner", "left", "right", "outer", "semi", "anti", "cross")
        if how not in allowed_how:
            raise ValueError(
                f"IbisJoin: how must be one of {list(allowed_how)}, got {how!r}"
            )
        if how == "cross":
            if predicates is not None:
                raise TypeError(
                    "IbisJoin: cross join takes no predicates"
                )
        else:
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
        self._predicates = predicates
        self._how = how
        super().__init__(left=left, right=right, _config=_config, **kwargs)

    @property
    def how(self) -> str:
        return self._how

    async def process(
        self, left: IbisTable, right: IbisTable, **_: Any
    ) -> IbisTable:
        """Join the left and right Ibis expressions on the configured predicates and return the result.

        Args:
            left: The left-side IbisTable.
            right: The right-side IbisTable to join against.

        Returns:
            A new IbisTable containing the joined deferred expression.
        """
        if self._how == "cross":
            joined = left.expression.cross_join(right.expression)
            return left.with_expression(joined)
        if callable(self._predicates):
            condition = self._predicates(left.expression, right.expression)
            joined = left.expression.join(
                right.expression, predicates=condition, how=self._how,
            )
        elif isinstance(self._predicates, str):
            joined = left.expression.join(
                right.expression, predicates=self._predicates, how=self._how,
            )
        else:
            assert self._predicates is not None
            joined = left.expression.join(
                right.expression,
                predicates=list(self._predicates),
                how=self._how,
            )
        return left.with_expression(joined)
