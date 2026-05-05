"""``IbisGroupByAggregate`` — Tier-3 group-by + aggregation that extends
the deferred expression with ``.group_by(...).aggregate(...)``.

The aggregation factory receives the upstream ``ibis.Table`` and returns
either a single named aggregation expression or a sequence of them::

    IbisGroupByAggregate(
        batch=upstream,
        by=("region",),
        aggregations=lambda t: t.amount.sum().name("total"),
        _config=KnotConfig(id="region_totals"),
    )

    IbisGroupByAggregate(
        batch=upstream,
        by=("region",),
        aggregations=lambda t: [
            t.amount.sum().name("total"),
            t.customer.nunique().name("n_customers"),
        ],
        _config=KnotConfig(id="region_metrics"),
    )

Algorithm:
    1. Validate that ``by`` is a non-empty sequence of non-empty strings.
    2. Validate that ``aggregations`` is callable.
    3. Invoke ``aggregations(expression)`` to produce one or more ``ibis.Expr`` values.
    4. Call ``expression.group_by(list(by)).aggregate(*result)`` or
       ``expression.group_by(list(by)).aggregate(result)`` depending on whether
       the factory returned a sequence.
    5. Return a new ``IbisTable`` wrapping the extended deferred expression.

    No rows are read from the backend — the aggregation becomes a SQL
    ``GROUP BY`` + aggregate clause when compiled and executed.

    ```text
    result = aggregations(expression)
    if isinstance(result, (list, tuple)):
        agg_expr = expression.group_by(list(by)).aggregate(*result)
    else:
        agg_expr = expression.group_by(list(by)).aggregate(result)
    return IbisTable(agg_expr)
    ```

References:
    [1] Ibis — Table.group_by / aggregate:
        https://ibis-project.org/reference/expression-tables.html#ibis.expr.types.relations.Table.group_by
    [2] Alternative: Dask groupby.agg (chosen Ibis for full SQL push-down):
        https://docs.dask.org/en/stable/dataframe-groupby.html
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

import ibis

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.lazy.ibis.ibis_table import IbisTable


class IbisGroupByAggregate(Knot):
    """Group rows and apply Ibis aggregation expressions."""

    def __init__(
        self,
        *,
        batch: Knot,
        by: Knot | Sequence[str],
        aggregations: Knot | Callable[[ibis.Table], Any],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            batch=batch,
            by=by,
            aggregations=aggregations,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        batch: IbisTable,
        by: Any,
        aggregations: Any,
        **_: Any,
    ) -> IbisTable:
        """Extend the deferred Ibis expression with a group-by aggregation and return the result.

        Args:
            batch: The upstream IbisTable whose expression will be aggregated.
            by: A sequence of column name strings to group by.
            aggregations: A callable (table) -> ibis.Expr or sequence of ibis.Expr.

        Returns:
            A new IbisTable with the group-by aggregation appended to the deferred expression.
        """
        if not isinstance(by, Sequence) or isinstance(by, (str, bytes)):
            raise TypeError(
                "IbisGroupByAggregate: by must be a sequence of column names"
            )
        if not by:
            raise ValueError("IbisGroupByAggregate: by must be non-empty")
        for column in by:
            if not isinstance(column, str) or not column:
                raise TypeError(
                    "IbisGroupByAggregate: every entry in by must be "
                    "a non-empty string"
                )
        if not callable(aggregations):
            raise TypeError(
                "IbisGroupByAggregate: aggregations must be a callable "
                "(table) -> ibis.Expr or sequence of ibis.Expr"
            )
        result = aggregations(batch.expression)
        if isinstance(result, (list, tuple)):
            aggregated = (
                batch.expression.group_by(list(by)).aggregate(*result)
            )
        else:
            aggregated = (
                batch.expression.group_by(list(by)).aggregate(result)
            )
        return batch.with_expression(aggregated)
