"""``RayCompute`` — terminal sink that materialises a deferred Ray Data
plan.

Three operating modes:

1. ``target_path`` is set + ``writer`` supplied: the sink calls
   ``writer(dataset, target_path, **writer_kwargs)`` (e.g.
   ``ray.data.Dataset.write_parquet``-style) and returns a
   :class:`RayExecutionReceipt`.
2. ``return_pandas=True``: the sink calls ``ds.to_pandas()`` and returns
   the resulting pandas DataFrame.
3. Default: the sink calls ``ds.materialize()`` and returns a
   :class:`RayExecutionReceipt` describing the execution.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

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
        target_path: str | None = None,
        writer: Callable[..., Any] | None = None,
        writer_kwargs: dict[str, Any] | None = None,
        return_pandas: bool = False,
        **kwargs: Any,
    ) -> None:
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
        self._target_path = target_path
        self._writer = writer
        self._writer_kwargs: dict[str, Any] = dict(writer_kwargs or {})
        self._return_pandas = return_pandas
        super().__init__(batch=batch, _config=_config, **kwargs)

    @property
    def target_path(self) -> str | None:
        return self._target_path

    @property
    def return_pandas(self) -> bool:
        return self._return_pandas

    async def process(self, batch: RayDataset, **_: Any) -> Any:
        if self._target_path is not None:
            assert self._writer is not None
            self._writer(batch.dataset, self._target_path, **self._writer_kwargs)
            return RayExecutionReceipt(
                backend_name=batch.backend_name,
                target_path=self._target_path,
                dataset_size=None,
                block_count=None,
                executed_at=datetime.now(timezone.utc),
            )

        if self._return_pandas:
            return batch.dataset.to_pandas()

        materialised = batch.dataset.materialize()
        return RayExecutionReceipt(
            backend_name=batch.backend_name,
            target_path=None,
            dataset_size=self._safe_count(materialised),
            block_count=self._safe_block_count(materialised),
            executed_at=datetime.now(timezone.utc),
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
