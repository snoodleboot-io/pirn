"""``PolarsAggregate`` — Tier-2 group-by + aggregation via Polars's native
``group_by`` / ``agg`` API.

Unlike Tier-1 :class:`pirn.domains.data.transforms.aggregate.Aggregate`,
this knot accepts a tuple of ``polars.Expr`` aggregation expressions
directly so users get the full power of Polars (any expression, including
``pl.col(x).sum().alias("total")``, conditional aggregations, struct
aggregations, etc.).

Algorithm:
    1. Validate ``by`` as a non-empty sequence of non-empty strings via
       :class:`IdentifierValidator`.
    2. Validate ``aggs`` as a non-empty sequence of ``polars.Expr``
       objects.
    3. Call ``frame.group_by(by, maintain_order=True)`` to group rows
       while preserving insertion order.
    4. Apply the aggregation expressions via ``.agg(list(aggs))``.
    5. Return the result wrapped in a new :class:`PolarsDataBatch`.

References:
    [1] Polars — DataFrame.group_by:
        https://docs.pola.rs/api/python/stable/reference/dataframe/api/polars.DataFrame.group_by.html
    [2] Polars — GroupBy.agg:
        https://docs.pola.rs/api/python/stable/reference/dataframe/api/polars.GroupBy.agg.html
    [3] Alternative: pandas GroupBy.agg (chosen Polars here for vectorised,
        lazy-compatible execution and native Expr vocabulary):
        https://pandas.pydata.org/docs/reference/api/pandas.core.groupby.DataFrameGroupBy.agg.html
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import polars as pl

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.frames.polars.polars_data_batch import PolarsDataBatch
from pirn.domains.data.identifier_validator import IdentifierValidator


class PolarsAggregate(Knot):
    """Group rows by ``by`` and apply Polars aggregation expressions."""

    def __init__(
        self,
        *,
        batch: Knot,
        by: Knot | Sequence[str],
        aggs: Knot | Sequence[pl.Expr],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(batch=batch, by=by, aggs=aggs, _config=_config, **kwargs)

    async def process(
        self,
        batch: PolarsDataBatch,
        by: Any,
        aggs: Any,
        **_: Any,
    ) -> PolarsDataBatch:
        """Group the batch by the configured columns and apply the Polars aggregation expressions.

        Args:
            batch: The PolarsDataBatch to group and aggregate.
            by: Sequence of column names to group by.
            aggs: Sequence of polars.Expr aggregation expressions.

        Returns:
            A new PolarsDataBatch containing the aggregated result.
        """
        IdentifierValidator.validate_columns("PolarsAggregate.by", by)
        if not isinstance(aggs, Sequence) or isinstance(aggs, (str, bytes)):
            raise TypeError("PolarsAggregate: aggs must be a sequence of polars.Expr")
        if not aggs:
            raise ValueError("PolarsAggregate: aggs must be non-empty")
        for expression in aggs:
            if not isinstance(expression, pl.Expr):
                raise TypeError(
                    "PolarsAggregate: every entry in aggs must be a polars.Expr; "
                    f"got {type(expression).__name__}"
                )
        grouped = batch.frame.group_by(list(by), maintain_order=True)
        return batch.with_frame(grouped.agg(list(aggs)))
