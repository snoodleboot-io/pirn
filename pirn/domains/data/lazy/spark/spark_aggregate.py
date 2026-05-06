"""``SparkAggregate`` — Tier-3 group-by + aggregation over a deferred
Spark plan.

The declarative form uses a mapping ``output_col -> (input_col, fn)``
where ``fn`` is one of the supported aggregation function names. Each
entry is materialised to a ``pyspark.sql.functions.<fn>(input).alias(output)``
column inside ``DataFrame.groupBy(...).agg(...)``. Result remains
deferred.

Algorithm:
    1. Validate ``by`` — a non-empty sequence of valid column identifier
       strings, checked via :class:`IdentifierValidator`.
    2. Validate ``aggs`` — a non-empty mapping of
       ``output_col -> (input_col, fn)`` where ``fn`` is one of the
       allowed aggregation function names.
    3. Build a list of PySpark column expressions:
       ``spark_functions.<fn>(input_col).alias(output_col)``.
    4. Call ``frame.groupBy(*by).agg(*agg_columns)`` to extend the
       deferred Spark plan.
    5. Return the result wrapped in a new :class:`SparkDataFrame`.

    ```text
    for output_col, (input_col, fn) in aggs:
        col_expr = spark_functions.<fn>(input_col).alias(output_col)
    grouped = frame.groupBy(*by)
    aggregated = grouped.agg(*col_exprs)
    return SparkDataFrame(frame=aggregated)
    ```

References:
    [1] PySpark — DataFrame.groupBy:
        https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/api/pyspark.sql.DataFrame.groupBy.html
    [2] PySpark — DataFrame.agg:
        https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/api/pyspark.sql.DataFrame.agg.html
    [3] PySpark — pyspark.sql.functions aggregation reference:
        https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/functions/aggregate_functions.html
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.identifier_validator import IdentifierValidator
from pirn.domains.data.lazy.spark.spark_dataframe import SparkDataFrame


class SparkAggregate(Knot):
    """Group rows and apply Spark aggregation functions. Output is deferred."""

    _allowed_fns: ClassVar[frozenset[str]] = frozenset(
        {
            "sum",
            "min",
            "max",
            "mean",
            "count",
            "count_distinct",
            "first",
            "last",
        }
    )

    def __init__(
        self,
        *,
        frame: Knot,
        by: Knot | Sequence[str],
        aggs: Knot | Mapping[str, tuple[str, str]],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(frame=frame, by=by, aggs=aggs, _config=_config, **kwargs)

    async def process(
        self,
        frame: Any,  # SparkDataFrame — pydantic can't schema pyspark types
        by: Any,  # Sequence[str]
        aggs: Any,  # Mapping[str, tuple[str, str]]
        **_: Any,
    ) -> SparkDataFrame:
        """Apply the configured group-by and aggregation functions to the deferred Spark frame.

        Args:
            frame: The upstream SparkDataFrame whose plan will be extended with the aggregation.
            by: Column name(s) to group by.
            aggs: Mapping of ``output_col -> (input_col, fn)`` aggregation specs.

        Returns:
            A new SparkDataFrame wrapping the grouped and aggregated deferred Spark plan.
        """
        try:
            from pyspark.sql import functions as spark_functions
        except ImportError as exc:
            raise ImportError(
                "SparkAggregate requires pyspark; install with `pip install pirn[spark]`"
            ) from exc
        IdentifierValidator.validate_columns("SparkAggregate.by", by)
        if not isinstance(aggs, Mapping) or not aggs:
            raise TypeError(
                "SparkAggregate: aggs must be a non-empty mapping of output_col -> (input_col, fn)"
            )
        for output_col, spec in aggs.items():
            IdentifierValidator.validate_column("SparkAggregate: output column", output_col)
            if (
                not isinstance(spec, tuple)
                or len(spec) != 2
                or not isinstance(spec[0], str)
                or not isinstance(spec[1], str)
            ):
                raise TypeError(
                    f"SparkAggregate: aggs[{output_col!r}] must be (input_col, fn) — both strings"
                )
            input_col, fn = spec
            IdentifierValidator.validate_column(
                f"SparkAggregate: aggs[{output_col!r}] input column",
                input_col,
            )
            if fn not in self._allowed_fns:
                raise ValueError(
                    f"SparkAggregate: aggs[{output_col!r}] fn must be one of "
                    f"{sorted(self._allowed_fns)!r}, got {fn!r}"
                )
        by_list = list(by)
        agg_columns = []
        for output_col, (input_col, fn) in aggs.items():
            spark_fn = getattr(spark_functions, fn)
            agg_columns.append(spark_fn(input_col).alias(output_col))
        grouped = frame.frame.groupBy(*by_list)
        aggregated = grouped.agg(*agg_columns)
        return frame.with_frame(aggregated)
