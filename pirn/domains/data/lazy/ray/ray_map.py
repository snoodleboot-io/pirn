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

Algorithm:
    1. Validate that ``fn`` is callable.
    2. Validate ``batch_format`` is a string when supplied.
    3. Validate ``batch_size`` is a positive int when supplied.
    4. Build a kwargs dict from any non-None optional parameters.
    5. Call ``dataset.map_batches(fn, **kwargs)`` to extend the deferred plan.
    6. Return the result wrapped in a new :class:`RayDataset`.

    ```text
    kwargs = {}
    if batch_format: kwargs["batch_format"] = batch_format
    if batch_size:   kwargs["batch_size"]   = batch_size
    out = dataset.map_batches(fn, **kwargs)
    return RayDataset(dataset=out)
    ```

References:
    [1] Ray Data — Dataset.map_batches:
        https://docs.ray.io/en/latest/data/api/doc/ray.data.Dataset.map_batches.html
    [2] Ray Data — batch formats (numpy, pandas, pyarrow):
        https://docs.ray.io/en/latest/data/transforming-data.html#configuring-batch-format
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.lazy.ray.ray_dataset import RayDataset


class RayMap(Knot):
    """Apply ``ds.map_batches(fn)`` to a deferred Ray Dataset."""

    def __init__(
        self,
        *,
        batch: Knot,
        fn: Knot | Callable[..., Any],
        _config: KnotConfig,
        batch_format: Knot | str | None = None,
        batch_size: Knot | int | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            batch=batch,
            fn=fn,
            batch_format=batch_format,
            batch_size=batch_size,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        batch: RayDataset,
        fn: Any,  # Callable[..., Any] — pydantic can't schema Callable
        batch_format: str | None,
        batch_size: int | None,
        **_: Any,
    ) -> RayDataset:
        """Extend the deferred Ray Dataset plan with a map_batches transform.

        Args:
            batch: The upstream RayDataset whose plan will be extended.
            fn: A callable applied to each batch of the dataset.
            batch_format: Optional format hint (e.g. ``"numpy"``).
            batch_size: Optional number of rows per batch.

        Returns:
            A new RayDataset wrapping the extended deferred plan.
        """
        if not callable(fn):
            raise TypeError("RayMap: fn must be a callable (batch) -> batch")
        if batch_format is not None and not isinstance(batch_format, str):
            raise TypeError("RayMap: batch_format must be a string or None")
        if batch_size is not None and (
            not isinstance(batch_size, int) or batch_size <= 0
        ):
            raise ValueError("RayMap: batch_size must be a positive int")
        map_kwargs: dict[str, Any] = {}
        if batch_format is not None:
            map_kwargs["batch_format"] = batch_format
        if batch_size is not None:
            map_kwargs["batch_size"] = batch_size
        return batch.with_dataset(batch.dataset.map_batches(fn, **map_kwargs))
