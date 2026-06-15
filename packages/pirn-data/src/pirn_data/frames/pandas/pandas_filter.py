"""``PandasFilter`` — Tier-2 row predicate using a callable that returns a
boolean mask.

Pandas does not have a native expression syntax like Polars. Instead,
this knot expects a callable ``predicate(df) -> pandas.Series[bool]``
(or any boolean-mask-like indexer accepted by ``df[mask]``). The
callable is applied once to the whole frame, so vectorised mask
construction is preferred (e.g.
``lambda df: df["region"] == "EU"``).

Example::

    PandasFilter(
        batch=upstream,
        predicate=lambda df: df["region"] == "EU",
        _config=KnotConfig(id="eu_only"),
    )

Algorithm:
    1. Validate that ``predicate`` is callable.
    2. Invoke ``predicate(batch.frame)`` to produce a boolean mask.
    3. Apply the mask with ``frame[mask]`` and reset the integer index.
    4. Return the filtered frame wrapped in a new :class:`PandasDataBatch`.

References:
    [1] pandas — Boolean indexing:
        https://pandas.pydata.org/docs/user_guide/indexing.html#boolean-indexing
    [2] Alternative: pandas DataFrame.query (string expressions); chosen
        callable approach to avoid SQL-injection-like risks with string eval:
        https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.query.html
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_data.frames.pandas.pandas_data_batch import PandasDataBatch


class PandasFilter(Knot):
    """Apply a callable boolean-mask predicate to a :class:`PandasDataBatch`."""

    def __init__(
        self,
        *,
        batch: Knot,
        predicate: Knot | Callable[..., Any],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(batch=batch, predicate=predicate, _config=_config, **kwargs)

    async def process(
        self,
        batch: PandasDataBatch,
        predicate: Any,
        **_: Any,
    ) -> PandasDataBatch:
        """Apply the callable predicate to produce a boolean mask and return the filtered batch.

        Args:
            batch: The PandasDataBatch to filter.
            predicate: A callable ``(df) -> pandas.Series[bool]``.

        Returns:
            A new PandasDataBatch containing only the rows for which the predicate returns True.
        """
        if not callable(predicate):
            raise TypeError(
                "PandasFilter: predicate must be a callable "
                "(df) -> pandas.Series[bool]; for row-by-row Python callables "
                "use the Tier-1 pirn_data.transforms.filter.Filter knot instead"
            )
        mask = predicate(batch.frame)
        return batch.with_frame(batch.frame[mask].reset_index(drop=True))  # type: ignore[arg-type]
