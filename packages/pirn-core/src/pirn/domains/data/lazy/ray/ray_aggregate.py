"""``RayAggregate`` — Tier-3 group-by + aggregation over a deferred
``ray.data.Dataset``.

Two construction modes:

1. ``aggregator: Callable[[ray.data.Dataset], ray.data.Dataset]`` — caller
   supplies a transform that does any group-by / aggregate they like.
2. ``by`` + ``aggs`` — declarative form. ``aggs`` must be a sequence of
   ray.data.aggregate-compatible aggregations (e.g.
   ``[ray.data.aggregate.Sum("amount")]``).

Algorithm:
    Callable mode:

    1. Validate that ``aggregator`` is callable.
    2. Invoke ``aggregator(dataset)`` and return the resulting dataset
       wrapped in a new :class:`RayDataset`.

    Declarative mode:

    1. Validate ``by`` — must be a non-empty string or non-empty sequence
       of non-empty strings.
    2. Validate ``aggs`` — must be a non-empty sequence.
    3. Call ``dataset.groupby(by).aggregate(*aggs)`` and return the
       result wrapped in a new :class:`RayDataset`.

    ```text
    if aggregator:
        out = aggregator(dataset)
    else:
        out = dataset.groupby(by).aggregate(*aggs)
    return RayDataset(dataset=out)
    ```

References:
    [1] Ray Data — groupby and aggregate:
        https://docs.ray.io/en/latest/data/api/doc/ray.data.Dataset.groupby.html
    [2] Ray Data — map / custom aggregation:
        https://docs.ray.io/en/latest/data/transforming-data.html
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

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
        aggregator: Knot | Callable[[ray.data.Dataset], ray.data.Dataset] | None = None,
        by: Knot | str | Sequence[str] | None = None,
        aggs: Knot | Sequence[Any] | None = None,
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
        batch: RayDataset,
        aggregator: Any,  # Callable[[ray.data.Dataset], ray.data.Dataset] | None
        by: Any,  # str | Sequence[str] | None
        aggs: Any,  # Sequence[Any] | None
        **_: Any,
    ) -> RayDataset:
        """Apply group-by aggregation to the deferred Ray Dataset and return the updated dataset.

        Args:
            batch: The upstream RayDataset to aggregate.
            aggregator: A callable ``(dataset) -> dataset`` for free-form aggregation,
                or ``None`` when using declarative ``by``/``aggs``.
            by: Column name(s) to group by (declarative mode).
            aggs: Sequence of ray.data.aggregate aggregations (declarative mode).

        Returns:
            A new RayDataset wrapping the aggregated Ray Data plan.
        """
        if aggregator is None and by is None:
            raise TypeError("RayAggregate: either aggregator or (by, aggs) must be supplied")
        if aggregator is not None and (by is not None or aggs is not None):
            raise TypeError("RayAggregate: aggregator is mutually exclusive with by/aggs")
        if aggregator is not None:
            if not callable(aggregator):
                raise TypeError("RayAggregate: aggregator must be a callable (dataset) -> dataset")
            aggregated = aggregator(batch.dataset)
            return batch.with_dataset(aggregated)  # type: ignore[arg-type]

        # Declarative mode
        if isinstance(by, str):
            if not by:
                raise ValueError("RayAggregate: by must be non-empty")
            resolved_by: str | list[str] = by
        elif isinstance(by, Sequence):
            if not by:
                raise ValueError("RayAggregate: by must be non-empty")
            for column in by:
                if not isinstance(column, str) or not column:
                    raise TypeError("RayAggregate: every entry in by must be a non-empty string")
            resolved_by = list(by)
        else:
            raise TypeError("RayAggregate: by must be a column name or sequence of names")
        if aggs is None:
            raise TypeError("RayAggregate: aggs is required when by is supplied")
        if not isinstance(aggs, Sequence) or isinstance(aggs, (str, bytes)):
            raise TypeError("RayAggregate: aggs must be a sequence of ray.data.aggregate instances")
        if not aggs:
            raise ValueError("RayAggregate: aggs must be non-empty")
        grouped = batch.dataset.groupby(resolved_by)
        aggregated = grouped.aggregate(*aggs)
        return batch.with_dataset(aggregated)
