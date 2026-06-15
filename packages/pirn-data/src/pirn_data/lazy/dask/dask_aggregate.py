"""``DaskAggregate`` — Tier-3 group-by + aggregation over a deferred Dask
graph.

Two construction modes:

1. ``aggregator: Callable[[dd.DataFrame], dd.DataFrame]`` — caller
   supplies a transform that does any group-by / aggregate / reset_index
   they like. Most flexible::

        DaskAggregate(
            batch=upstream,
            aggregator=lambda frame: frame.groupby("region")
                                          .amount.sum()
                                          .reset_index(),
            _config=KnotConfig(id="totals"),
        )

2. ``by`` + ``aggs`` — declarative form, equivalent to
   ``frame.groupby(by).agg(aggs).reset_index()``::

        DaskAggregate(
            batch=upstream,
            by=("region",),
            aggs={"amount": "sum"},
            _config=KnotConfig(id="totals"),
        )

Algorithm:
    Two mutually exclusive paths:

    **Callable path** (``aggregator`` is set):

    1. Validate that ``aggregator`` is callable.
    2. Call ``aggregator(frame)`` to produce the aggregated deferred frame.
    3. Return a new ``DaskDataFrame`` wrapping the result.

    **Declarative path** (``by`` + ``aggs`` are set):

    1. Validate that ``by`` is a non-empty sequence of non-empty strings.
    2. Validate that ``aggs`` is a non-empty dict.
    3. Call ``frame.groupby(list(by)).agg(aggs).reset_index()``.
    4. Return a new ``DaskDataFrame`` wrapping the result.

    No partitions are computed — the result is still a deferred Dask graph.

    ```text
    if aggregator:
        out = aggregator(frame)
    else:
        out = frame.groupby(list(by)).agg(aggs).reset_index()
    return DaskDataFrame(out)
    ```

References:
    [1] Dask DataFrame — groupby and aggregation:
        https://docs.dask.org/en/stable/dataframe-groupby.html
    [2] Dask DataFrame.agg:
        https://docs.dask.org/en/stable/generated/dask.dataframe.DataFrame.agg.html
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

import dask.dataframe as dd
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_data.lazy.dask.dask_dataframe import DaskDataFrame


class DaskAggregate(Knot):
    """Group rows and apply Dask aggregations.  Result remains deferred."""

    def __init__(
        self,
        *,
        batch: Knot,
        _config: KnotConfig,
        aggregator: Knot | Callable[[dd.DataFrame], dd.DataFrame] | None = None,
        by: Knot | Sequence[str] | None = None,
        aggs: Knot | dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            batch=batch,
            aggregator=aggregator,
            by=by,
            aggs=aggs,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        batch: DaskDataFrame,
        aggregator: Any,
        by: Any,
        aggs: Any,
        **_: Any,
    ) -> DaskDataFrame:
        """Apply group-by aggregation to the deferred Dask frame and return the updated lazy frame.

        Args:
            batch: The upstream DaskDataFrame to aggregate.
            aggregator: A callable (frame) -> dd.DataFrame, or None.
            by: A sequence of column names for declarative mode, or None.
            aggs: A dict of aggregations for declarative mode, or None.

        Returns:
            A new DaskDataFrame wrapping the aggregated, still-deferred Dask graph.
        """
        if aggregator is None and by is None:
            raise TypeError("DaskAggregate: either aggregator or (by, aggs) must be supplied")
        if aggregator is not None and (by is not None or aggs is not None):
            raise TypeError("DaskAggregate: aggregator is mutually exclusive with by/aggs")
        if aggregator is not None:
            if not callable(aggregator):
                raise TypeError(
                    "DaskAggregate: aggregator must be a callable "
                    "(frame) -> dask.dataframe.DataFrame"
                )
            aggregated = aggregator(batch.frame)
        else:
            if isinstance(by, (str, bytes)) or not isinstance(by, Sequence):
                raise TypeError("DaskAggregate: by must be a sequence of column names")
            if not by:
                raise ValueError("DaskAggregate: by must be non-empty")
            for column in by:
                if not isinstance(column, str) or not column:
                    raise TypeError("DaskAggregate: every entry in by must be a non-empty string")
            if aggs is None:
                raise TypeError("DaskAggregate: aggs is required when by is supplied")
            if not isinstance(aggs, dict) or not aggs:
                raise TypeError("DaskAggregate: aggs must be a non-empty dict")
            _grouped = batch.frame.groupby(list(by)).agg(aggs)
            if _grouped is None:
                raise RuntimeError("DaskAggregate: groupby().agg() returned None")
            aggregated = _grouped.reset_index()  # type: ignore[arg-type]
        return batch.with_frame(aggregated)  # type: ignore[arg-type]
