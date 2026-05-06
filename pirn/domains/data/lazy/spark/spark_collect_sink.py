"""``SparkCollectSink`` — terminal sink that materialises a deferred
Spark plan to driver memory.

.. warning::
    ``frame.collect()`` pulls every row to the Spark driver. For large
    frames this can OOM the driver process. Use ``max_rows`` to bound
    the collection, or prefer :class:`SparkWriteSink` for production
    materialisation.

The optional ``max_rows`` parameter is a safety net: the sink calls
``frame.limit(max_rows + 1).collect()`` and raises
:class:`ValueError` if the result exceeds the bound (so the caller is
informed rather than silently truncated).

Algorithm:
    1. If ``max_rows`` is supplied, validate it is a positive integer.
    2. Bounded mode: call ``frame.limit(max_rows + 1).collect()``. If
       the result has more than ``max_rows`` rows, raise ``ValueError``
       rather than silently truncating.
    3. Unbounded mode: call ``frame.collect()`` directly.
    4. Convert each PySpark ``Row`` to a plain dict via
       ``row.asDict(recursive=True)`` and return the list.

    ```text
    if max_rows:
        rows = frame.limit(max_rows + 1).collect()
        if len(rows) > max_rows: raise ValueError(...)
    else:
        rows = frame.collect()
    return [row.asDict(recursive=True) for row in rows]
    ```

References:
    [1] PySpark — DataFrame.collect:
        https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/api/pyspark.sql.DataFrame.collect.html
    [2] PySpark — DataFrame.limit:
        https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/api/pyspark.sql.DataFrame.limit.html
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.sink import Sink


class SparkCollectSink(Sink):
    """Materialise a deferred Spark DataFrame; return rows as ``list[dict]``."""

    def __init__(
        self,
        *,
        frame: Knot,
        _config: KnotConfig,
        max_rows: Knot | int | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(frame=frame, max_rows=max_rows, _config=_config, **kwargs)

    async def process(
        self,
        frame: Any,  # SparkDataFrame — pydantic can't schema pyspark types
        max_rows: int | None,
        **_: Any,
    ) -> list[dict[str, Any]]:
        """Collect the Spark DataFrame rows to driver memory and return them as a list of dicts.

        Args:
            frame: The upstream SparkDataFrame to materialise.
            max_rows: Optional upper bound on collected rows; raises if exceeded.

        Returns:
            A list of dicts, one per row, with column names as keys.

        Raises:
            TypeError: If max_rows is not an int.
            ValueError: If max_rows is not positive, or if the frame exceeds the bound.
        """
        if max_rows is not None:
            if not isinstance(max_rows, int) or isinstance(max_rows, bool):
                raise TypeError("SparkCollectSink: max_rows must be an int or None")
            if max_rows <= 0:
                raise ValueError("SparkCollectSink: max_rows must be positive")
            bounded = frame.frame.limit(max_rows + 1).collect()
            if len(bounded) > max_rows:
                raise ValueError(
                    f"SparkCollectSink: frame produced more than max_rows="
                    f"{max_rows} rows; refusing to collect"
                )
            rows = bounded
        else:
            rows = frame.frame.collect()
        return [row.asDict(recursive=True) for row in rows]
