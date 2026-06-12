"""``SparkWriteSink`` — terminal sink that materialises a deferred
Spark plan to disk via ``DataFrame.write``.

Returns a :class:`SparkExecutionReceipt` recording the output path and
completion timestamp. ``row_count`` is left ``None`` to avoid a second
pass over the (often very large) result.

Algorithm:
    1. Validate that ``path`` is a non-empty string.
    2. Validate that ``format`` is a non-empty string.
    3. Validate that ``mode`` is a non-empty string.
    4. Call ``frame.write.mode(mode).format(format).save(path)`` to
       materialise the deferred plan to disk.
    5. Return a :class:`SparkExecutionReceipt` with
       ``succeeded=True``, ``row_count=None``, and the output path.

    ```text
    frame.write.mode(mode).format(format).save(path)
    return SparkExecutionReceipt(succeeded=True, output_path=path, ...)
    ```

References:
    [1] PySpark — DataFrameWriter.save:
        https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/api/pyspark.sql.DataFrameWriter.save.html
    [2] PySpark — DataFrameWriter.mode:
        https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/api/pyspark.sql.DataFrameWriter.mode.html
    [3] PySpark — DataFrameWriter.format:
        https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/api/pyspark.sql.DataFrameWriter.format.html
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
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
        path: Knot | str,
        _config: KnotConfig,
        format: Knot | str = "parquet",
        mode: Knot | str = "overwrite",
        **kwargs: Any,
    ) -> None:
        super().__init__(
            frame=frame,
            path=path,
            format=format,
            mode=mode,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        frame: Any,  # SparkDataFrame — pydantic can't schema pyspark types
        path: str,
        format: str,
        mode: str,
        **_: Any,
    ) -> SparkExecutionReceipt:
        """Write the deferred Spark DataFrame to the configured path.

        Returns an execution receipt recording the output path and timestamp.

        Args:
            frame: The upstream SparkDataFrame whose deferred plan will be materialised to disk.
            path: Destination path.
            format: Output format (e.g. ``"parquet"``, ``"csv"``).
            mode: Write mode (e.g. ``"overwrite"``, ``"append"``).

        Returns:
            A SparkExecutionReceipt recording the output path and completion timestamp.
        """
        if not isinstance(path, str) or not path:
            raise ValueError("SparkWriteSink: path must be a non-empty string")
        if not isinstance(format, str) or not format:
            raise ValueError("SparkWriteSink: format must be a non-empty string")
        if not isinstance(mode, str) or not mode:
            raise ValueError("SparkWriteSink: mode must be a non-empty string")
        frame.frame.write.mode(mode).format(format).save(path)
        return SparkExecutionReceipt(
            succeeded=True,
            row_count=None,
            output_path=path,
            completed_at=datetime.now(UTC),
        )
