"""``PolarsAggregate`` — Tier-2 group-by + aggregation via Polars's native
``group_by`` / ``agg`` API.

Unlike Tier-1 :class:`pirn.domains.data.transforms.aggregate.Aggregate`,
this knot accepts a tuple of ``polars.Expr`` aggregation expressions
directly so users get the full power of Polars (any expression, including
``pl.col(x).sum().alias("total")``, conditional aggregations, struct
aggregations, etc.).
"""

from __future__ import annotations

from typing import Any, Sequence

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
        by: Sequence[str],
        aggs: Sequence[pl.Expr],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        IdentifierValidator.validate_columns("PolarsAggregate.by", by)
        if not isinstance(aggs, Sequence) or isinstance(aggs, (str, bytes)):
            raise TypeError(
                "PolarsAggregate: aggs must be a sequence of polars.Expr"
            )
        if not aggs:
            raise ValueError("PolarsAggregate: aggs must be non-empty")
        for expression in aggs:
            if not isinstance(expression, pl.Expr):
                raise TypeError(
                    "PolarsAggregate: every entry in aggs must be a polars.Expr; "
                    f"got {type(expression).__name__}"
                )
        self._by: tuple[str, ...] = tuple(by)
        self._aggs: tuple[pl.Expr, ...] = tuple(aggs)
        super().__init__(batch=batch, _config=_config, **kwargs)

    @property
    def by(self) -> tuple[str, ...]:
        return self._by

    @property
    def aggs(self) -> tuple[pl.Expr, ...]:
        return self._aggs

    async def process(self, batch: PolarsDataBatch, **_: Any) -> PolarsDataBatch:
        grouped = batch.frame.group_by(list(self._by), maintain_order=True)
        return batch.with_frame(grouped.agg(list(self._aggs)))
