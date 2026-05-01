"""``SparkWriteSink`` — terminal sink that materialises a deferred
Spark plan to disk via ``DataFrame.write``.

Returns a :class:`SparkExecutionReceipt` recording the output path and
completion timestamp. ``row_count`` is left ``None`` to avoid a second
pass over the (often very large) result.
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


class SparkWriteSink(Sink):
    """Persist a deferred Spark DataFrame; return a receipt."""

    def __init__(
        self,
        *,
        frame: Knot,
        path: str,
        _config: KnotConfig,
        format: str = "parquet",
        mode: str = "overwrite",
        **kwargs: Any,
    ) -> None:
        try:
            import pyspark.sql  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "SparkWriteSink requires pyspark; install with `pip install pirn[spark]`"
            ) from exc
        if not isinstance(path, str) or not path:
            raise ValueError("SparkWriteSink: path must be a non-empty string")
        if not isinstance(format, str) or not format:
            raise ValueError("SparkWriteSink: format must be a non-empty string")
        if not isinstance(mode, str) or not mode:
            raise ValueError("SparkWriteSink: mode must be a non-empty string")
        self._path = path
        self._format = format
        self._mode = mode
        super().__init__(frame=frame, _config=_config, **kwargs)

    @property
    def path(self) -> str:
        return self._path

    @property
    def format(self) -> str:
        return self._format

    @property
    def mode(self) -> str:
        return self._mode

    async def process(
        self, frame: SparkDataFrame, **_: Any
    ) -> SparkExecutionReceipt:
        frame.frame.write.mode(self._mode).format(self._format).save(self._path)
        return SparkExecutionReceipt(
            succeeded=True,
            row_count=None,
            output_path=self._path,
            completed_at=datetime.now(timezone.utc),
        )
