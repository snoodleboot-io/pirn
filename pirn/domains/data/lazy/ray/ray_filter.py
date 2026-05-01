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
"""

from __future__ import annotations

from typing import Any, Callable

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.lazy.ray.ray_dataset import RayDataset


class RayFilter(Knot):
    """Apply ``ds.filter(predicate)`` to a deferred Ray Dataset."""

    def __init__(
        self,
        *,
        batch: Knot,
        predicate: Callable[[dict[str, Any]], bool],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not callable(predicate):
            raise TypeError(
                "RayFilter: predicate must be a callable (row) -> bool"
            )
        self._predicate = predicate
        super().__init__(batch=batch, _config=_config, **kwargs)

    @property
    def predicate(self) -> Callable[[dict[str, Any]], bool]:
        return self._predicate

    async def process(self, batch: RayDataset, **_: Any) -> RayDataset:
        return batch.with_dataset(batch.dataset.filter(self._predicate))
