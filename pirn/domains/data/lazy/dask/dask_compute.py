"""``DaskCompute`` — terminal sink that materialises a deferred Dask
graph.

Three operating modes:

1. ``target_path`` is set + ``writer`` supplied: the sink calls
   ``writer(frame, target_path, **writer_kwargs)`` (e.g.
   ``dask.dataframe.DataFrame.to_parquet``) and returns a
   :class:`DaskExecutionReceipt`.
2. ``return_pandas=True``: the sink calls ``frame.compute()`` and
   returns the resulting pandas DataFrame directly — useful for
   downstream Tier-1/2 consumers.
3. Default: the sink calls ``frame.compute()``, discards the result, and
   returns a :class:`DaskExecutionReceipt` summarising the execution.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.lazy.dask.dask_dataframe import DaskDataFrame
from pirn.domains.data.lazy.dask.dask_execution_receipt import (
    DaskExecutionReceipt,
)
from pirn.nodes.sink import Sink


class DaskCompute(Sink):
    """Compute the deferred Dask graph and return a receipt or pandas frame."""

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
            raise TypeError("DaskCompute: target_path must be a string or None")
        if target_path is not None and not target_path:
            raise ValueError("DaskCompute: target_path must be non-empty when set")
        if target_path is not None and writer is None:
            raise TypeError(
                "DaskCompute: writer is required when target_path is set "
                "(e.g. writer=dask.dataframe.DataFrame.to_parquet style)"
            )
        if writer is not None and not callable(writer):
            raise TypeError("DaskCompute: writer must be callable")
        if return_pandas and target_path is not None:
            raise TypeError(
                "DaskCompute: return_pandas and target_path are mutually exclusive"
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

    async def process(self, batch: DaskDataFrame, **_: Any) -> Any:
        partitions = batch.npartitions

        if self._target_path is not None:
            assert self._writer is not None
            self._writer(batch.frame, self._target_path, **self._writer_kwargs)
            return DaskExecutionReceipt(
                backend_name=batch.backend_name,
                target_path=self._target_path,
                partitions_executed=partitions,
                row_count=None,
                executed_at=datetime.now(timezone.utc),
            )

        materialised = batch.frame.compute()
        row_count = self._row_count(materialised)
        if self._return_pandas:
            return materialised
        return DaskExecutionReceipt(
            backend_name=batch.backend_name,
            target_path=None,
            partitions_executed=partitions,
            row_count=row_count,
            executed_at=datetime.now(timezone.utc),
        )

    @staticmethod
    def _row_count(value: Any) -> int | None:
        try:
            return len(value)
        except TypeError:
            return None
