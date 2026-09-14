"""``SparkFilter`` — Tier-3 row predicate that extends the deferred
Spark logical plan with a SQL ``WHERE`` clause.

The predicate is a Spark SQL expression string (e.g. ``"age > 18"``)
passed verbatim to ``DataFrame.filter``. Spark parses and pushes the
predicate down through the plan; nothing is computed here.

Algorithm:
    1. Validate that ``predicate`` is a non-empty string.
    2. Call ``frame.filter(predicate)`` to extend the deferred Spark plan.
    3. Return the result wrapped in a new :class:`SparkDataFrame`.

    ```text
    filtered = frame.filter(predicate)
    return SparkDataFrame(frame=filtered)
    ```

References:
    [1] PySpark — DataFrame.filter:
        https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/api/pyspark.sql.DataFrame.filter.html
    [2] Spark SQL — expressions and predicate push-down:
        https://spark.apache.org/docs/latest/sql-ref-syntax-qry-select-where.html
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_data.lazy.spark.spark_dataframe import SparkDataFrame


class SparkFilter(Knot):
    """Apply ``frame.filter(predicate)`` to a deferred Spark DataFrame."""

    def __init__(
        self,
        *,
        frame: Knot,
        predicate: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(frame=frame, predicate=predicate, _config=_config, **kwargs)

    async def process(
        self,
        frame: Any,  # SparkDataFrame — pydantic can't schema pyspark types
        predicate: str,
        **_: Any,
    ) -> SparkDataFrame:
        """Apply the SQL predicate to the deferred Spark frame and return the filtered result.

        Args:
            frame: The upstream SparkDataFrame to filter.
            predicate: A Spark SQL expression string.

        Returns:
            A new SparkDataFrame with the SQL WHERE predicate applied to the deferred plan.
        """
        if not isinstance(predicate, str):
            raise TypeError("SparkFilter: predicate must be a Spark SQL expression string")
        if not predicate.strip():
            raise ValueError("SparkFilter: predicate must be non-empty")
        return frame.with_frame(frame.frame.filter(predicate))
