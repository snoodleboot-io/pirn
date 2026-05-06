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

Algorithm:
    1. Validate group-by column identifiers and the ``aggs`` mapping.
    2. Build ``group_exprs`` from ``by`` column names.
    3. For each entry in ``aggs``: resolve the expression (call the callable
       if needed) and alias it to the output column name.
    4. Call ``frame.aggregate(group_exprs, agg_exprs)`` and return the result.

References:
    [1] Apache DataFusion Python — DataFrame.aggregate:
        https://datafusion.apache.org/python/autoapi/datafusion/index.html#datafusion.DataFrame.aggregate
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

import datafusion as df

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.frames.datafusion.datafusion_data_batch import (
    DatafusionDataBatch,
)
from pirn.domains.data.identifier_validator import IdentifierValidator


class DatafusionAggregate(Knot):
    """Group rows by ``by`` and apply DataFusion aggregation expressions."""

    def __init__(
        self,
        *,
        batch: Knot,
        by: Knot | Sequence[str],
        aggs: Knot | Mapping[str, df.Expr | Callable[[df.DataFrame], df.Expr]],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(batch=batch, by=by, aggs=aggs, _config=_config, **kwargs)

    async def process(
        self,
        batch: DatafusionDataBatch,
        by: Sequence[str],
        aggs: Any,  # Mapping[str, df.Expr | Callable[...]] — pydantic can't schema df.Expr
        **_: Any,
    ) -> DatafusionDataBatch:
        """Group the batch and apply aggregation expressions.

        Args:
            batch: The DatafusionDataBatch to group and aggregate.
            by: Column names to group on.
            aggs: Mapping of output column name to DataFusion expression or
                callable producing one.

        Returns:
            A new DatafusionDataBatch containing the aggregated result.
        """
        IdentifierValidator.validate_columns("DatafusionAggregate.by", by)
        if not isinstance(aggs, Mapping) or not aggs:
            raise TypeError(
                "DatafusionAggregate: aggs must be a non-empty Mapping"
                "[output_name, datafusion.Expr | callable]"
            )
        for output, expression in aggs.items():
            IdentifierValidator.validate_column("DatafusionAggregate: output column", output)
            if not (isinstance(expression, df.Expr) or callable(expression)):
                raise TypeError(
                    f"DatafusionAggregate: aggs[{output!r}] must be a "
                    "datafusion.Expr or callable(frame) -> datafusion.Expr"
                )

        group_exprs = [df.col(column) for column in by]
        agg_exprs: list[df.Expr] = []
        for output, expression in aggs.items():
            expr = expression(batch.frame) if callable(expression) else expression
            agg_exprs.append(expr.alias(output))  # type: ignore[attr-defined]
        aggregated = batch.frame.aggregate(group_exprs, agg_exprs)
        return batch.with_frame(aggregated)
