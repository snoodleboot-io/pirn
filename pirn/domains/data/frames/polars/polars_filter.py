"""``PolarsFilter`` — Tier-2 row predicate using a native Polars expression.

Unlike Tier-1 :class:`pirn.domains.data.transforms.filter.Filter` (which
takes a Python callable per row), this knot expects a
``polars.Expr`` so the engine can apply the predicate vectorised across
the frame.

Example::

    PolarsFilter(
        batch=upstream,
        expression=pl.col("region") == "EU",
        _config=KnotConfig(id="eu_only"),
    )
"""

from __future__ import annotations

from typing import Any

import polars as pl

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.frames.polars.polars_data_batch import PolarsDataBatch


class PolarsFilter(Knot):
    """Apply a Polars predicate expression to a :class:`PolarsDataBatch`."""

    def __init__(
        self,
        *,
        batch: Knot,
        expression: pl.Expr,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(expression, pl.Expr):
            raise TypeError(
                "PolarsFilter: expression must be a polars.Expr; "
                "for row-by-row Python callables use the Tier-1 "
                "pirn.domains.data.transforms.filter.Filter knot instead"
            )
        self._expression = expression
        super().__init__(batch=batch, _config=_config, **kwargs)

    @property
    def expression(self) -> pl.Expr:
        return self._expression

    async def process(self, batch: PolarsDataBatch, **_: Any) -> PolarsDataBatch:
        return batch.with_frame(batch.frame.filter(self._expression))
