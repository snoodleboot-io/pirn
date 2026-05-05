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

Algorithm:
    1. Validate that ``predicate`` is callable.
    2. Invoke ``predicate(expression)`` to produce an ``ibis.Expr`` filter condition.
    3. Call ``expression.filter(condition)`` to extend the deferred expression tree.
    4. Return a new ``IbisTable`` wrapping the filtered expression.

    No rows are read from the backend — the predicate becomes a SQL ``WHERE``
    clause when the expression is eventually compiled and executed.

    ```text
    condition = predicate(expression)
    return IbisTable(expression.filter(condition))
    ```

References:
    [1] Ibis — Table.filter:
        https://ibis-project.org/reference/expression-tables.html#ibis.expr.types.relations.Table.filter
    [2] Alternative: Dask boolean masking (chosen Ibis here for full SQL push-down):
        https://docs.dask.org/en/stable/dataframe-indexing.html
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

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
        predicate: Knot | Callable[[ibis.Table], ibis.Expr],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(batch=batch, predicate=predicate, _config=_config, **kwargs)

    async def process(self, batch: IbisTable, predicate: Any, **_: Any) -> IbisTable:
        """Apply the callable predicate to extend the deferred Ibis expression with a filter.

        Args:
            batch: The upstream IbisTable whose expression will be filtered.
            predicate: A callable (table) -> ibis.Expr.

        Returns:
            A new IbisTable with the filter predicate appended to the deferred expression.
        """
        if not callable(predicate):
            raise TypeError(
                "IbisFilter: predicate must be a callable (table) -> ibis.Expr"
            )
        expression = predicate(batch.expression)
        return batch.with_expression(batch.expression.filter(expression))
