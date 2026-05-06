"""``RayFilter`` — Tier-3 row predicate that extends the deferred
``ray.data.Dataset`` plan with ``ds.filter(predicate)``.

The predicate is a callable that takes a single record (dict) and
returns a bool::

    RayFilter(
        batch=upstream,
        predicate=lambda row: row["region"] == "EU",
        _config=KnotConfig(id="eu_only"),
    )

No blocks are computed here — Ray Data simply extends the plan.

Algorithm:
    1. Validate that ``predicate`` is callable.
    2. Call ``dataset.filter(predicate)`` to extend the deferred plan.
    3. Return the result wrapped in a new :class:`RayDataset`.

    ```text
    out = dataset.filter(predicate)
    return RayDataset(dataset=out)
    ```

References:
    [1] Ray Data — Dataset.filter:
        https://docs.ray.io/en/latest/data/api/doc/ray.data.Dataset.filter.html
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.lazy.ray.ray_dataset import RayDataset


class RayFilter(Knot):
    """Apply ``ds.filter(predicate)`` to a deferred Ray Dataset."""

    def __init__(
        self,
        *,
        batch: Knot,
        predicate: Knot | Callable[[dict[str, Any]], bool],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(batch=batch, predicate=predicate, _config=_config, **kwargs)

    async def process(
        self,
        batch: RayDataset,
        predicate: Any,  # Callable[[dict[str, Any]], bool] — pydantic can't schema Callable
        **_: Any,
    ) -> RayDataset:
        """Apply the row-level callable predicate to filter the deferred Ray Dataset plan.

        Args:
            batch: The upstream RayDataset to filter.
            predicate: A callable ``(row) -> bool`` applied to each row.

        Returns:
            A new RayDataset with the filter predicate applied to the deferred plan.
        """
        if not callable(predicate):
            raise TypeError("RayFilter: predicate must be a callable (row) -> bool")
        return batch.with_dataset(batch.dataset.filter(predicate))
