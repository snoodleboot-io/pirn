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

Algorithm:
    1. Validate ``windows`` as a non-empty sequence of ``polars.Expr``
       objects.
    2. Call ``frame.with_columns(list(windows))`` to evaluate the window
       expressions and append them as new named columns.
    3. Return the extended frame wrapped in a new :class:`PolarsDataBatch`.

References:
    [1] Polars — DataFrame.with_columns:
        https://docs.pola.rs/api/python/stable/reference/dataframe/api/polars.DataFrame.with_columns.html
    [2] Polars — window functions (over):
        https://docs.pola.rs/user-guide/expressions/window-functions/
    [3] Polars — rolling aggregations:
        https://docs.pola.rs/user-guide/expressions/aggregation/
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import polars as pl
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_data.frames.polars.polars_data_batch import PolarsDataBatch


class PolarsWindowCalc(Knot):
    """Append window-expression columns to a :class:`PolarsDataBatch`."""

    def __init__(
        self,
        *,
        batch: Knot,
        windows: Knot | Sequence[pl.Expr],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(batch=batch, windows=windows, _config=_config, **kwargs)

    async def process(
        self,
        batch: PolarsDataBatch,
        windows: Any,
        **_: Any,
    ) -> PolarsDataBatch:
        """Evaluate the configured window expressions and append them as new columns to the batch.

        Args:
            batch: The upstream PolarsDataBatch to extend with window columns.
            windows: Sequence of polars.Expr window expressions.

        Returns:
            A new PolarsDataBatch with the window expression columns appended.
        """
        if not isinstance(windows, Sequence) or isinstance(windows, (str, bytes)):
            raise TypeError("PolarsWindowCalc: windows must be a sequence of polars.Expr")
        if not windows:
            raise ValueError("PolarsWindowCalc: windows must be non-empty")
        for expression in windows:
            if not isinstance(expression, pl.Expr):
                raise TypeError(
                    "PolarsWindowCalc: every entry in windows must be a polars.Expr; "
                    f"got {type(expression).__name__}"
                )
        return batch.with_frame(batch.frame.with_columns(list(windows)))
