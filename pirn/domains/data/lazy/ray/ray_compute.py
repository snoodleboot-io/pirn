"""``RayCompute`` — terminal sink that materialises a deferred Ray Data plan.

Three operating modes:

1. ``target_path`` is set + ``writer`` supplied: the sink calls
   ``writer(dataset, target_path, **writer_kwargs)`` and returns a
   :class:`RayExecutionReceipt`.
2. ``return_pandas=True``: the sink calls ``ds.to_pandas()`` and returns
   the resulting pandas DataFrame.
3. Default: the sink calls ``ds.materialize()`` and returns a
   :class:`RayExecutionReceipt` describing the execution.

Algorithm:
    1. Validate inputs: ``target_path`` must be a non-empty string when set;
       ``writer`` must be callable when ``target_path`` is set;
       ``return_pandas`` and ``target_path`` are mutually exclusive.
    2. Write mode: call ``writer(dataset, target_path, **writer_kwargs)``
       and return a :class:`RayExecutionReceipt` with the target path.
    3. Pandas mode: call ``dataset.to_pandas()`` and return the DataFrame.
    4. Default: call ``dataset.materialize()``, extract row and block counts
       via safe accessors, and return a :class:`RayExecutionReceipt`.

    ```text
    if target_path:
        writer(dataset, target_path, **writer_kwargs)
        return RayExecutionReceipt(target_path=target_path, ...)
    elif return_pandas:
        return dataset.to_pandas()
    else:
        mat = dataset.materialize()
        return RayExecutionReceipt(dataset_size=count(mat), ...)
    ```

References:
    [1] Ray Data — materialize:
        https://docs.ray.io/en/latest/data/api/doc/ray.data.Dataset.materialize.html
    [2] Ray Data — write_parquet and other write methods:
        https://docs.ray.io/en/latest/data/api/doc/ray.data.Dataset.write_parquet.html
    [3] Ray Data — to_pandas:
        https://docs.ray.io/en/latest/data/api/doc/ray.data.Dataset.to_pandas.html
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.lazy.ray.ray_dataset import RayDataset
from pirn.domains.data.lazy.ray.ray_execution_receipt import (
    RayExecutionReceipt,
)
from pirn.nodes.sink import Sink


class RayCompute(Sink):
    """Materialise a deferred Ray Dataset and return a receipt or pandas frame."""

    def __init__(
        self,
        *,
        batch: Knot,
        _config: KnotConfig,
        target_path: Knot | str | None = None,
        writer: Knot | Callable[..., Any] | None = None,
        writer_kwargs: Knot | dict[str, Any] | None = None,
        return_pandas: Knot | bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            batch=batch,
            target_path=target_path,
            writer=writer,
            writer_kwargs=writer_kwargs,
            return_pandas=return_pandas,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        batch: RayDataset,
        target_path: str | None,
        writer: Any,  # Callable[..., Any] | None — pydantic can't schema Callable
        writer_kwargs: dict[str, Any] | None,
        return_pandas: bool,
        **_: Any,
    ) -> Any:
        """Materialise the Ray Dataset plan and return a receipt or pandas frame.

        Args:
            batch: The upstream RayDataset whose plan will be materialised.
            target_path: Destination path when writing to disk, or ``None``.
            writer: A callable ``(dataset, path, **kw)`` used for writing, or ``None``.
            writer_kwargs: Extra keyword arguments forwarded to ``writer``.
            return_pandas: When ``True``, return ``ds.to_pandas()`` instead of a receipt.

        Returns:
            A RayExecutionReceipt if writing to disk or materialising without
            return_pandas, or a pandas DataFrame when return_pandas is True.
        """
        if target_path is not None and not isinstance(target_path, str):
            raise TypeError("RayCompute: target_path must be a string or None")
        if target_path is not None and not target_path:
            raise ValueError("RayCompute: target_path must be non-empty when set")
        if target_path is not None and writer is None:
            raise TypeError(
                "RayCompute: writer is required when target_path is set "
                "(e.g. writer=lambda ds, p: ds.write_parquet(p))"
            )
        if writer is not None and not callable(writer):
            raise TypeError("RayCompute: writer must be callable")
        if return_pandas and target_path is not None:
            raise TypeError(
                "RayCompute: return_pandas and target_path are mutually exclusive"
            )
        resolved_kwargs: dict[str, Any] = dict(writer_kwargs or {})

        if target_path is not None:
            assert writer is not None
            writer(batch.dataset, target_path, **resolved_kwargs)
            return RayExecutionReceipt(
                backend_name=batch.backend_name,
                target_path=target_path,
                dataset_size=None,
                block_count=None,
                executed_at=datetime.now(UTC),
            )

        if return_pandas:
            return batch.dataset.to_pandas()

        materialised = batch.dataset.materialize()
        return RayExecutionReceipt(
            backend_name=batch.backend_name,
            target_path=None,
            dataset_size=self._safe_count(materialised),
            block_count=self._safe_block_count(materialised),
            executed_at=datetime.now(UTC),
        )

    @staticmethod
    def _safe_count(dataset: Any) -> int | None:
        try:
            return int(dataset.count())
        except Exception:
            return None

    @staticmethod
    def _safe_block_count(dataset: Any) -> int | None:
        for attr in ("num_blocks",):
            method = getattr(dataset, attr, None)
            if callable(method):
                try:
                    return int(method())
                except Exception:
                    return None
        return None
