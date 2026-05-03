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
"""

from __future__ import annotations

from typing import Any, Callable, Sequence

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
        by: Sequence[str],
        aggregations: Callable[[ibis.Table], Any],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
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
        self._by: tuple[str, ...] = tuple(by)
        self._aggregations = aggregations
        super().__init__(batch=batch, _config=_config, **kwargs)

    @property
    def by(self) -> tuple[str, ...]:
        return self._by

    async def process(self, batch: IbisTable, **_: Any) -> IbisTable:
        """Extend the deferred Ibis expression with a group-by aggregation and return the result.

        Args:
            batch: The upstream IbisTable whose expression will be aggregated.

        Returns:
            A new IbisTable with the group-by aggregation appended to the deferred expression.
        """
        result = self._aggregations(batch.expression)
        if isinstance(result, (list, tuple)):
            aggregated = (
                batch.expression.group_by(list(self._by)).aggregate(*result)
            )
        else:
            aggregated = (
                batch.expression.group_by(list(self._by)).aggregate(result)
            )
        return batch.with_expression(aggregated)
