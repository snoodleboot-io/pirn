"""``DatafusionAggregate`` — Tier-2 group-by + aggregation via
:meth:`datafusion.DataFrame.aggregate`.

The caller passes:

* ``by``: tuple of column names to group on,
* ``aggs``: mapping of *output column name* → DataFusion aggregation
  expression. Each value may be either:
    - a :class:`datafusion.Expr` (e.g. ``df.functions.sum(df.col("amount"))``), or
    - a callable ``(datafusion.DataFrame) -> datafusion.Expr`` invoked at
      process time so the expression can be built against the upstream
      frame's columns.

Each aggregation expression is automatically aliased to the configured
output name. Output column names go through the same identifier check
as the group-by columns so they are safe to use as field aliases.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Mapping, Sequence

import datafusion as df

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.frames.datafusion.datafusion_data_batch import (
    DatafusionDataBatch,
)


class DatafusionAggregate(Knot):
    """Group rows by ``by`` and apply DataFusion aggregation expressions."""

    def __init__(
        self,
        *,
        batch: Knot,
        by: Sequence[str],
        aggs: Mapping[str, df.Expr | Callable[[df.DataFrame], df.Expr]],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(by, Sequence) or isinstance(by, (str, bytes)):
            raise TypeError(
                "DatafusionAggregate: by must be a sequence of column names"
            )
        if not by:
            raise ValueError("DatafusionAggregate: by must be non-empty")
        identifier_re = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
        for column in by:
            if not isinstance(column, str) or not column:
                raise TypeError(
                    "DatafusionAggregate: every entry in by must be a non-empty string"
                )
            if not identifier_re.match(column):
                raise ValueError(
                    f"DatafusionAggregate: by entry {column!r} is not a plain identifier"
                )
        if not isinstance(aggs, Mapping) or not aggs:
            raise TypeError(
                "DatafusionAggregate: aggs must be a non-empty Mapping"
                "[output_name, datafusion.Expr | callable]"
            )
        for output, expression in aggs.items():
            if not isinstance(output, str) or not output:
                raise TypeError(
                    "DatafusionAggregate: aggs keys must be non-empty strings"
                )
            if not identifier_re.match(output):
                raise ValueError(
                    f"DatafusionAggregate: output column {output!r} is not a plain identifier"
                )
            if not (isinstance(expression, df.Expr) or callable(expression)):
                raise TypeError(
                    f"DatafusionAggregate: aggs[{output!r}] must be a "
                    "datafusion.Expr or callable(frame) -> datafusion.Expr"
                )
        self._by: tuple[str, ...] = tuple(by)
        self._aggs: dict[str, df.Expr | Callable[[df.DataFrame], df.Expr]] = dict(aggs)
        super().__init__(batch=batch, _config=_config, **kwargs)

    @property
    def by(self) -> tuple[str, ...]:
        return self._by

    async def process(
        self, batch: DatafusionDataBatch, **_: Any
    ) -> DatafusionDataBatch:
        group_exprs = [df.col(column) for column in self._by]
        agg_exprs: list[df.Expr] = []
        for output, expression in self._aggs.items():
            expr = expression(batch.frame) if callable(expression) else expression
            agg_exprs.append(expr.alias(output))
        aggregated = batch.frame.aggregate(group_exprs, agg_exprs)
        return batch.with_frame(aggregated)
