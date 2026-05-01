"""``SparkAggregate`` — Tier-3 group-by + aggregation over a deferred
Spark plan.

The declarative form uses a mapping ``output_col -> (input_col, fn)``
where ``fn`` is one of the supported aggregation function names. Each
entry is materialised to a ``pyspark.sql.functions.<fn>(input).alias(output)``
column inside ``DataFrame.groupBy(...).agg(...)``. Result remains
deferred.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.lazy.spark.spark_dataframe import SparkDataFrame


class SparkAggregate(Knot):
    """Group rows and apply Spark aggregation functions. Output is deferred."""

    _ALLOWED_FNS: ClassVar[frozenset[str]] = frozenset(
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
    _IDENT_RE: ClassVar[re.Pattern[str]] = re.compile(
        r"^[A-Za-z_][A-Za-z0-9_]*$"
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
            import pyspark.sql  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "SparkAggregate requires pyspark; install with `pip install pirn[spark]`"
            ) from exc
        if isinstance(by, (str, bytes)) or not isinstance(by, Sequence):
            raise TypeError(
                "SparkAggregate: by must be a sequence of column names"
            )
        if not by:
            raise ValueError("SparkAggregate: by must be non-empty")
        for column in by:
            if not isinstance(column, str) or not self._IDENT_RE.match(column):
                raise ValueError(
                    f"SparkAggregate: invalid group-by column name {column!r}"
                )
        if not isinstance(aggs, Mapping) or not aggs:
            raise TypeError(
                "SparkAggregate: aggs must be a non-empty mapping of "
                "output_col -> (input_col, fn)"
            )
        for output_col, spec in aggs.items():
            if not isinstance(output_col, str) or not self._IDENT_RE.match(
                output_col
            ):
                raise ValueError(
                    f"SparkAggregate: invalid output column name {output_col!r}"
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
            if not self._IDENT_RE.match(input_col):
                raise ValueError(
                    f"SparkAggregate: invalid input column name {input_col!r}"
                )
            if fn not in self._ALLOWED_FNS:
                raise ValueError(
                    f"SparkAggregate: aggs[{output_col!r}] fn must be one of "
                    f"{sorted(self._ALLOWED_FNS)!r}, got {fn!r}"
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
        from pyspark.sql import functions as F

        agg_columns = []
        for output_col, (input_col, fn) in self._aggs.items():
            spark_fn = getattr(F, fn)
            agg_columns.append(spark_fn(input_col).alias(output_col))
        grouped = frame.frame.groupBy(*self._by)
        aggregated = grouped.agg(*agg_columns)
        return frame.with_frame(aggregated)
