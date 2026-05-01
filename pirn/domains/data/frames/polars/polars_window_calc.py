"""``PolarsWindowCalc`` — rolling/expanding/cumulative window aggregations
expressed as Polars expressions.

Polars's window operations are first-class on ``Expr``: ``rolling_*``,
``cum_*``, and partition-aware windows via ``.over(...)``. Rather than
invent a parallel vocabulary, this knot lets the caller pass arbitrary
window expressions — same idiom as :class:`PolarsAggregate` — and
appends them as new columns via ``with_columns``.

Two common shapes covered by examples in tests:

- *Cumulative / rolling*: ``pl.col("amount").rolling_mean(window_size=3).alias("avg3")``
- *Partitioned ranking*: ``pl.col("amount").rank().over("region").alias("rank_in_region")``
"""

from __future__ import annotations

from typing import Any, Sequence

import polars as pl

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.frames.polars.polars_data_batch import PolarsDataBatch


class PolarsWindowCalc(Knot):
    """Append window-expression columns to a :class:`PolarsDataBatch`."""

    def __init__(
        self,
        *,
        batch: Knot,
        windows: Sequence[pl.Expr],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(windows, Sequence) or isinstance(windows, (str, bytes)):
            raise TypeError(
                "PolarsWindowCalc: windows must be a sequence of polars.Expr"
            )
        if not windows:
            raise ValueError("PolarsWindowCalc: windows must be non-empty")
        for expression in windows:
            if not isinstance(expression, pl.Expr):
                raise TypeError(
                    "PolarsWindowCalc: every entry in windows must be a polars.Expr; "
                    f"got {type(expression).__name__}"
                )
        self._windows: tuple[pl.Expr, ...] = tuple(windows)
        super().__init__(batch=batch, _config=_config, **kwargs)

    @property
    def windows(self) -> tuple[pl.Expr, ...]:
        return self._windows

    async def process(self, batch: PolarsDataBatch, **_: Any) -> PolarsDataBatch:
        return batch.with_frame(batch.frame.with_columns(list(self._windows)))
