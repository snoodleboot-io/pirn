"""``SparkAggregate`` — Tier-3 group-by + aggregation over a deferred
Spark plan.

The declarative form uses a mapping ``output_col -> (input_col, fn)``
where ``fn`` is one of the supported aggregation function names. Each
entry is materialised to a ``pyspark.sql.functions.<fn>(input).alias(output)``
column inside ``DataFrame.groupBy(...).agg(...)``. Result remains
deferred.
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
        by: Sequence[str],
        aggs: Mapping[str, tuple[str, str]],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        try:
            from pyspark.sql import functions as spark_functions
        except ImportError as exc:
            raise ImportError(
                "SparkAggregate requires pyspark; install with `pip install pirn[spark]`"
            ) from exc
        self._spark_functions = spark_functions
        IdentifierValidator.validate_columns("SparkAggregate.by", by)
        if not isinstance(aggs, Mapping) or not aggs:
            raise TypeError(
                "SparkAggregate: aggs must be a non-empty mapping of "
                "output_col -> (input_col, fn)"
            )
        for output_col, spec in aggs.items():
            IdentifierValidator.validate_column(
                "SparkAggregate: output column", output_col
            )
            if (
                not isinstance(spec, tuple)
                or len(spec) != 2
                or not isinstance(spec[0], str)
                or not isinstance(spec[1], str)
            ):
                raise TypeError(
                    f"SparkAggregate: aggs[{output_col!r}] must be "
                    "(input_col, fn) — both strings"
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
        self._by: tuple[str, ...] = tuple(by)
        self._aggs: dict[str, tuple[str, str]] = {
            out: (inp, fn) for out, (inp, fn) in aggs.items()
        }
        super().__init__(frame=frame, _config=_config, **kwargs)

    @property
    def by(self) -> tuple[str, ...]:
        return self._by

    @property
    def aggs(self) -> Mapping[str, tuple[str, str]]:
        return dict(self._aggs)

    async def process(self, frame: SparkDataFrame, **_: Any) -> SparkDataFrame:
        agg_columns = []
        for output_col, (input_col, fn) in self._aggs.items():
            spark_fn = getattr(self._spark_functions, fn)
            agg_columns.append(spark_fn(input_col).alias(output_col))
        grouped = frame.frame.groupBy(*self._by)
        aggregated = grouped.agg(*agg_columns)
        return frame.with_frame(aggregated)
