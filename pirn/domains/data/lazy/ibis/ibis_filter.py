"""``IbisFilter`` — Tier-3 row predicate that extends the deferred
expression with ``.filter(...)``.

Critically, *no rows are read from the engine* when this knot runs — the
Ibis expression simply grows. Materialisation happens at a terminal sink
(:class:`IbisToTable`), which compiles the whole graph to one SQL/Plan
and ships it to the backend.

The predicate is supplied as a callable that receives the upstream
``ibis.Table`` and returns an ``ibis.Expr``::

    IbisFilter(
        batch=upstream,
        predicate=lambda t: t.region == "EU",
        _config=KnotConfig(id="eu_only"),
    )
"""

from __future__ import annotations

from typing import Any, Callable

import ibis

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.lazy.ibis.ibis_table import IbisTable


class IbisFilter(Knot):
    """Apply ``ibis.Table.filter(...)`` to a deferred expression."""

    def __init__(
        self,
        *,
        batch: Knot,
        predicate: Callable[[ibis.Table], ibis.Expr],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not callable(predicate):
            raise TypeError(
                "IbisFilter: predicate must be a callable (table) -> ibis.Expr"
            )
        self._predicate = predicate
        super().__init__(batch=batch, _config=_config, **kwargs)

    @property
    def predicate(self) -> Callable[[ibis.Table], ibis.Expr]:
        return self._predicate

    async def process(self, batch: IbisTable, **_: Any) -> IbisTable:
        """Apply the callable predicate to extend the deferred Ibis expression with a filter.

        Args:
            batch: The upstream IbisTable whose expression will be filtered.

        Returns:
            A new IbisTable with the filter predicate appended to the deferred expression.
        """
        expression = self._predicate(batch.expression)
        return batch.with_expression(batch.expression.filter(expression))
