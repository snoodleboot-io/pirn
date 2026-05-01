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
"""

from __future__ import annotations

from typing import Any, Callable, Sequence

import dask.dataframe as dd

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.lazy.dask.dask_dataframe import DaskDataFrame


class DaskAggregate(Knot):
    """Group rows and apply Dask aggregations.  Result remains deferred."""

    def __init__(
        self,
        *,
        batch: Knot,
        _config: KnotConfig,
        aggregator: Callable[[dd.DataFrame], dd.DataFrame] | None = None,
        by: Sequence[str] | None = None,
        aggs: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        if aggregator is None and by is None:
            raise TypeError(
                "DaskAggregate: either aggregator or (by, aggs) must be supplied"
            )
        if aggregator is not None and (by is not None or aggs is not None):
            raise TypeError(
                "DaskAggregate: aggregator is mutually exclusive with by/aggs"
            )
        if aggregator is not None and not callable(aggregator):
            raise TypeError(
                "DaskAggregate: aggregator must be a callable "
                "(frame) -> dask.dataframe.DataFrame"
            )
        if by is not None:
            if isinstance(by, (str, bytes)) or not isinstance(by, Sequence):
                raise TypeError(
                    "DaskAggregate: by must be a sequence of column names"
                )
            if not by:
                raise ValueError("DaskAggregate: by must be non-empty")
            for column in by:
                if not isinstance(column, str) or not column:
                    raise TypeError(
                        "DaskAggregate: every entry in by must be a non-empty string"
                    )
            if aggs is None:
                raise TypeError(
                    "DaskAggregate: aggs is required when by is supplied"
                )
            if not isinstance(aggs, dict) or not aggs:
                raise TypeError(
                    "DaskAggregate: aggs must be a non-empty dict"
                )
        self._aggregator = aggregator
        self._by: tuple[str, ...] | None = tuple(by) if by is not None else None
        self._aggs: dict[str, Any] | None = dict(aggs) if aggs is not None else None
        super().__init__(batch=batch, _config=_config, **kwargs)

    @property
    def by(self) -> tuple[str, ...] | None:
        return self._by

    async def process(self, batch: DaskDataFrame, **_: Any) -> DaskDataFrame:
        if self._aggregator is not None:
            aggregated = self._aggregator(batch.frame)
        else:
            assert self._by is not None and self._aggs is not None
            aggregated = (
                batch.frame.groupby(list(self._by))
                .agg(self._aggs)
                .reset_index()
            )
        return batch.with_frame(aggregated)
