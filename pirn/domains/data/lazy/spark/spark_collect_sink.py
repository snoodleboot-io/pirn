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
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.lazy.spark.spark_dataframe import SparkDataFrame
from pirn.nodes.sink import Sink


class SparkCollectSink(Sink):
    """Materialise a deferred Spark DataFrame; return rows as ``list[dict]``."""

    def __init__(
        self,
        *,
        frame: Knot,
        _config: KnotConfig,
        max_rows: int | None = None,
        **kwargs: Any,
    ) -> None:
        try:
            import pyspark.sql  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "SparkCollectSink requires pyspark; install with `pip install pirn[spark]`"
            ) from exc
        if max_rows is not None:
            if not isinstance(max_rows, int) or isinstance(max_rows, bool):
                raise TypeError("SparkCollectSink: max_rows must be an int or None")
            if max_rows <= 0:
                raise ValueError("SparkCollectSink: max_rows must be positive")
        self._max_rows = max_rows
        super().__init__(frame=frame, _config=_config, **kwargs)

    @property
    def max_rows(self) -> int | None:
        return self._max_rows

    async def process(
        self, frame: SparkDataFrame, **_: Any
    ) -> list[dict[str, Any]]:
        if self._max_rows is None:
            rows = frame.frame.collect()
        else:
            bounded = frame.frame.limit(self._max_rows + 1).collect()
            if len(bounded) > self._max_rows:
                raise ValueError(
                    f"SparkCollectSink: frame produced more than max_rows="
                    f"{self._max_rows} rows; refusing to collect"
                )
            rows = bounded
        return [row.asDict(recursive=True) for row in rows]
