"""``SparkCompute`` — terminal sink that materialises a deferred Spark
plan.

Two operating modes:

1. ``path`` set: write the deferred frame to disk via
   ``frame.write.mode(mode).format(format).save(path)`` and return a
   :class:`SparkExecutionReceipt`. ``row_count`` is left ``None`` to
   avoid a second pass over the data.
2. Default (no ``path``): call ``frame.collect()`` to materialise the
   plan and return the list of ``pyspark.sql.Row`` objects.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.lazy.spark.spark_dataframe import SparkDataFrame
from pirn.domains.data.lazy.spark.spark_execution_receipt import (
    SparkExecutionReceipt,
)
from pirn.nodes.sink import Sink


class SparkCompute(Sink):
    """Materialise a deferred Spark DataFrame; return rows or a receipt."""

    def __init__(
        self,
        *,
        frame: Knot,
        _config: KnotConfig,
        path: str | None = None,
        format: str = "parquet",
        mode: str = "overwrite",
        **kwargs: Any,
    ) -> None:
        try:
            import pyspark.sql  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "SparkCompute requires pyspark; install with `pip install pirn[spark]`"
            ) from exc
        if path is not None:
            if not isinstance(path, str) or not path:
                raise ValueError("SparkCompute: path must be a non-empty string")
            if not isinstance(format, str) or not format:
                raise ValueError("SparkCompute: format must be a non-empty string")
            if not isinstance(mode, str) or not mode:
                raise ValueError("SparkCompute: mode must be a non-empty string")
        self._path = path
        self._format = format
        self._mode = mode
        super().__init__(frame=frame, _config=_config, **kwargs)

    @property
    def path(self) -> str | None:
        return self._path

    @property
    def format(self) -> str:
        return self._format

    @property
    def mode(self) -> str:
        return self._mode

    async def process(self, frame: SparkDataFrame, **_: Any) -> Any:
        if self._path is not None:
            try:
                frame.frame.write.mode(self._mode).format(self._format).save(
                    self._path
                )
            except BaseException:
                # Re-raise so the engine wraps as an Err; receipts are only
                # emitted on success.
                raise
            return SparkExecutionReceipt(
                succeeded=True,
                row_count=None,
                output_path=self._path,
                completed_at=datetime.now(timezone.utc),
            )

        rows = frame.frame.collect()
        return [row.asDict(recursive=True) for row in rows]
