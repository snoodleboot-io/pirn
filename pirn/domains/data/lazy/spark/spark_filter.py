"""``SparkFilter`` — Tier-3 row predicate that extends the deferred
Spark logical plan with a SQL ``WHERE`` clause.

The predicate is a Spark SQL expression string (e.g. ``"age > 18"``)
passed verbatim to ``DataFrame.filter``. Spark parses and pushes the
predicate down through the plan; nothing is computed here.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.lazy.spark.spark_dataframe import SparkDataFrame


class SparkFilter(Knot):
    """Apply ``frame.filter(predicate)`` to a deferred Spark DataFrame."""

    def __init__(
        self,
        *,
        frame: Knot,
        predicate: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        try:
            import pyspark.sql  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "SparkFilter requires pyspark; install with `pip install pirn[spark]`"
            ) from exc
        if not isinstance(predicate, str):
            raise TypeError(
                "SparkFilter: predicate must be a Spark SQL expression string"
            )
        if not predicate.strip():
            raise ValueError("SparkFilter: predicate must be non-empty")
        self._predicate = predicate
        super().__init__(frame=frame, _config=_config, **kwargs)

    @property
    def predicate(self) -> str:
        return self._predicate

    async def process(self, frame: SparkDataFrame, **_: Any) -> SparkDataFrame:
        return frame.with_frame(frame.frame.filter(self._predicate))
