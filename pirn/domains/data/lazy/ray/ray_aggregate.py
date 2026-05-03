"""``RayAggregate`` — Tier-3 group-by + aggregation over a deferred
``ray.data.Dataset``.

Two construction modes:

1. ``aggregator: Callable[[ray.data.Dataset], ray.data.Dataset]`` — caller
   supplies a transform that does any group-by / aggregate they like::

        RayAggregate(
            batch=upstream,
            aggregator=lambda ds: ds.groupby("region").sum("amount"),
            _config=KnotConfig(id="totals"),
        )

2. ``by`` + ``aggs`` — declarative form. ``aggs`` must be a sequence of
   ray.data.aggregate-compatible aggregations (e.g.
   ``[ray.data.aggregate.Sum("amount")]``)::

        from ray.data.aggregate import Sum
        RayAggregate(
            batch=upstream,
            by="region",
            aggs=[Sum("amount")],
            _config=KnotConfig(id="totals"),
        )
"""

from __future__ import annotations

from typing import Any, Callable, Sequence

import ray.data

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.lazy.ray.ray_dataset import RayDataset


class RayAggregate(Knot):
    """Group rows and apply Ray Data aggregations.  Result remains deferred."""

    def __init__(
        self,
        *,
        batch: Knot,
        _config: KnotConfig,
        aggregator: Callable[[ray.data.Dataset], ray.data.Dataset] | None = None,
        by: str | Sequence[str] | None = None,
        aggs: Sequence[Any] | None = None,
        **kwargs: Any,
    ) -> None:
        if aggregator is None and by is None:
            raise TypeError(
                "RayAggregate: either aggregator or (by, aggs) must be supplied"
            )
        if aggregator is not None and (by is not None or aggs is not None):
            raise TypeError(
                "RayAggregate: aggregator is mutually exclusive with by/aggs"
            )
        if aggregator is not None and not callable(aggregator):
            raise TypeError(
                "RayAggregate: aggregator must be a callable "
                "(dataset) -> dataset"
            )
        if by is not None:
            if isinstance(by, str):
                if not by:
                    raise ValueError("RayAggregate: by must be non-empty")
            elif isinstance(by, Sequence):
                if not by:
                    raise ValueError("RayAggregate: by must be non-empty")
                for column in by:
                    if not isinstance(column, str) or not column:
                        raise TypeError(
                            "RayAggregate: every entry in by must be a non-empty string"
                        )
            else:
                raise TypeError(
                    "RayAggregate: by must be a column name or sequence of names"
                )
            if aggs is None:
                raise TypeError(
                    "RayAggregate: aggs is required when by is supplied"
                )
            if not isinstance(aggs, Sequence) or isinstance(aggs, (str, bytes)):
                raise TypeError(
                    "RayAggregate: aggs must be a sequence of ray.data.aggregate "
                    "instances"
                )
            if not aggs:
                raise ValueError("RayAggregate: aggs must be non-empty")
        self._aggregator = aggregator
        self._by: str | tuple[str, ...] | None
        if isinstance(by, str):
            self._by = by
        elif by is not None:
            self._by = tuple(by)
        else:
            self._by = None
        self._aggs: tuple[Any, ...] | None = (
            tuple(aggs) if aggs is not None else None
        )
        super().__init__(batch=batch, _config=_config, **kwargs)

    @property
    def by(self) -> str | tuple[str, ...] | None:
        return self._by

    async def process(self, batch: RayDataset, **_: Any) -> RayDataset:
        """Apply group-by aggregation to the deferred Ray Dataset and return the updated dataset.

        Args:
            batch: The upstream RayDataset to aggregate.

        Returns:
            A new RayDataset wrapping the aggregated Ray Data plan.
        """
        if self._aggregator is not None:
            aggregated = self._aggregator(batch.dataset)
        else:
            assert self._by is not None and self._aggs is not None
            by = self._by if isinstance(self._by, str) else list(self._by)
            grouped = batch.dataset.groupby(by)
            aggregated = grouped.aggregate(*self._aggs)
        return batch.with_dataset(aggregated)
