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

Algorithm:
    1. Validate ``target_path`` (must be a non-empty string when set).
    2. Validate ``writer`` (required and callable when ``target_path`` is set).
    3. Validate mutual exclusion of ``return_pandas`` and ``target_path``.
    4. If ``target_path`` is set: call ``writer(frame, target_path, **writer_kwargs)``
       and return a :class:`DaskExecutionReceipt` with ``target_path`` recorded.
    5. Otherwise: call ``frame.compute()`` to materialise the deferred graph.
    6. If ``return_pandas``: return the computed pandas DataFrame directly.
    7. Otherwise: return a :class:`DaskExecutionReceipt` with ``row_count``.

    ```text
    if target_path:
        writer(frame, target_path, **writer_kwargs)
        return DaskExecutionReceipt(target_path=target_path, ...)
    materialised = frame.compute()
    if return_pandas:
        return materialised
    return DaskExecutionReceipt(row_count=len(materialised), ...)
    ```

References:
    [1] Dask DataFrame.compute — trigger materialisation:
        https://docs.dask.org/en/stable/generated/dask.dataframe.DataFrame.compute.html
    [2] Dask DataFrame.to_parquet — writer pattern:
        https://docs.dask.org/en/stable/generated/dask.dataframe.DataFrame.to_parquet.html
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

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
        batch: DaskDataFrame,
        target_path: Any,
        writer: Any,
        writer_kwargs: Any,
        return_pandas: Any,
        **_: Any,
    ) -> Any:
        """Trigger computation of the Dask graph and return a receipt or pandas frame.

        Args:
            batch: The upstream DaskDataFrame whose deferred graph will be computed.
            target_path: Optional file path to write results to.
            writer: A callable to write the frame when target_path is set.
            writer_kwargs: Extra keyword arguments forwarded to writer.
            return_pandas: If True, return the computed pandas DataFrame.

        Returns:
            A DaskExecutionReceipt if writing to disk or materialising without
            return_pandas, or a pandas DataFrame when return_pandas is True.
        """
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

        resolved_kwargs: dict[str, Any] = dict(writer_kwargs or {})
        partitions = batch.npartitions

        if target_path is not None:
            assert writer is not None
            writer(batch.frame, target_path, **resolved_kwargs)
            return DaskExecutionReceipt(
                backend_name=batch.backend_name,
                target_path=target_path,
                partitions_executed=partitions,
                row_count=None,
                executed_at=datetime.now(UTC),
            )

        materialised = batch.frame.compute()
        row_count = self._row_count(materialised)
        if return_pandas:
            return materialised
        return DaskExecutionReceipt(
            backend_name=batch.backend_name,
            target_path=None,
            partitions_executed=partitions,
            row_count=row_count,
            executed_at=datetime.now(UTC),
        )

    @staticmethod
    def _row_count(value: Any) -> int | None:
        try:
            return len(value)
        except TypeError:
            return None
