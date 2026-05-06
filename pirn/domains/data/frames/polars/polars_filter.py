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

Algorithm:
    1. Validate that ``expression`` is a ``polars.Expr``.
    2. Call ``frame.filter(expression)`` to apply the predicate
       vectorised across all rows.
    3. Return the filtered frame wrapped in a new :class:`PolarsDataBatch`.

References:
    [1] Polars — DataFrame.filter:
        https://docs.pola.rs/api/python/stable/reference/dataframe/api/polars.DataFrame.filter.html
    [2] Polars — Expressions:
        https://docs.pola.rs/user-guide/concepts/expressions/
    [3] Alternative: Tier-1 Filter with a Python callable per row (chosen
        Polars Expr here for vectorised execution without row iteration):
        pirn.domains.data.transforms.filter.Filter
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
        expression: Knot | Any,  # pl.Expr — pydantic-incompatible
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(batch=batch, expression=expression, _config=_config, **kwargs)

    async def process(
        self,
        batch: PolarsDataBatch,
        expression: Any,
        **_: Any,
    ) -> PolarsDataBatch:
        """Apply the Polars expression predicate to filter rows and return the resulting batch.

        Args:
            batch: The upstream PolarsDataBatch to filter.
            expression: A ``polars.Expr`` to use as the row filter.

        Returns:
            A new PolarsDataBatch containing only rows that satisfy the expression.
        """
        if not isinstance(expression, pl.Expr):
            raise TypeError(
                "PolarsFilter: expression must be a polars.Expr; "
                "for row-by-row Python callables use the Tier-1 "
                "pirn.domains.data.transforms.filter.Filter knot instead"
            )
        return batch.with_frame(batch.frame.filter(expression))
