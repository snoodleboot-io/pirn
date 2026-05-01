"""``RayMap`` — Tier-3 batch transform that extends the deferred
``ray.data.Dataset`` plan with ``ds.map_batches(fn)``.

The function operates on a batch — by default Ray Data hands it a
``pyarrow.Table`` or ``dict[str, np.ndarray]`` depending on
``batch_format``. Callers control that via ``batch_format``::

    RayMap(
        batch=upstream,
        fn=lambda b: {"x2": b["x"] * 2, **b},
        batch_format="numpy",
        _config=KnotConfig(id="double_x"),
    )

No blocks are computed here — the plan is extended lazily.
"""

from __future__ import annotations

from typing import Any, Callable

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.lazy.ray.ray_dataset import RayDataset


class RayMap(Knot):
    """Apply ``ds.map_batches(fn)`` to a deferred Ray Dataset."""

    def __init__(
        self,
        *,
        batch: Knot,
        fn: Callable[..., Any],
        _config: KnotConfig,
        batch_format: str | None = None,
        batch_size: int | None = None,
        **kwargs: Any,
    ) -> None:
        if not callable(fn):
            raise TypeError(
                "RayMap: fn must be a callable (batch) -> batch"
            )
        if batch_format is not None and not isinstance(batch_format, str):
            raise TypeError("RayMap: batch_format must be a string or None")
        if batch_size is not None and (
            not isinstance(batch_size, int) or batch_size <= 0
        ):
            raise ValueError("RayMap: batch_size must be a positive int")
        self._fn = fn
        self._batch_format = batch_format
        self._batch_size = batch_size
        super().__init__(batch=batch, _config=_config, **kwargs)

    async def process(self, batch: RayDataset, **_: Any) -> RayDataset:
        kwargs: dict[str, Any] = {}
        if self._batch_format is not None:
            kwargs["batch_format"] = self._batch_format
        if self._batch_size is not None:
            kwargs["batch_size"] = self._batch_size
        return batch.with_dataset(batch.dataset.map_batches(self._fn, **kwargs))
