"""``MetricLayerAggregator`` — computes a named metric with optional dimension slicing.

Supports sum, count, avg, and ratio aggregations. Returns a structured
metric record with name, value, dimensions, and computed_at timestamp.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Sequence

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.domains.data.identifier_validator import IdentifierValidator
from pirn.nodes.sub_tapestry import SubTapestry


class MetricLayerAggregator(SubTapestry):
    """Compute a named metric (sum/count/avg/ratio) with optional dimension slicing."""

    _supported_aggregations: frozenset[str] = frozenset({"sum", "count", "avg", "ratio"})

    def __init__(
        self,
        *,
        pool: DatabaseConnectionPool,
        source_table: str,
        metric_name: str,
        aggregation: Literal["sum", "count", "avg", "ratio"],
        value_column: str,
        dimension_columns: Sequence[str] = (),
        numerator_column: str = "",
        denominator_column: str = "",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(pool, DatabaseConnectionPool):
            raise TypeError(
                "MetricLayerAggregator: pool must be a DatabaseConnectionPool"
            )
        for label, value in (
            ("source_table", source_table),
            ("metric_name", metric_name),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(
                    f"MetricLayerAggregator: {label} must be a non-empty string"
                )
        if aggregation not in type(self)._supported_aggregations:
            raise ValueError(
                f"MetricLayerAggregator: aggregation must be one of "
                f"{sorted(type(self)._supported_aggregations)!r}, got {aggregation!r}"
            )
        IdentifierValidator.validate_column("source_table", source_table)
        if aggregation == "ratio":
            if not numerator_column or not denominator_column:
                raise ValueError(
                    "MetricLayerAggregator: ratio aggregation requires "
                    "numerator_column and denominator_column"
                )
            IdentifierValidator.validate_column(
                "numerator_column", numerator_column
            )
            IdentifierValidator.validate_column(
                "denominator_column", denominator_column
            )
        else:
            IdentifierValidator.validate_column("value_column", value_column)
        dim_tuple = tuple(dimension_columns)
        if dim_tuple:
            IdentifierValidator.validate_columns("dimension_columns", dim_tuple)
        self._pool = pool
        self._source_table = source_table
        self._metric_name = metric_name
        self._aggregation = aggregation
        self._value_column = value_column
        self._dimension_columns = dim_tuple
        self._numerator_column = numerator_column
        self._denominator_column = denominator_column
        super().__init__(_config=_config, **kwargs)

    def _build_query(self) -> str:
        if self._aggregation == "sum":
            agg_expr = f"SUM({self._value_column})"
        elif self._aggregation == "count":
            agg_expr = f"COUNT({self._value_column})"
        elif self._aggregation == "avg":
            agg_expr = f"AVG({self._value_column})"
        else:
            agg_expr = (
                f"CAST(SUM({self._numerator_column}) AS REAL) / "
                f"NULLIF(SUM({self._denominator_column}), 0)"
            )
        if self._dimension_columns:
            dim_list = ", ".join(self._dimension_columns)
            return (
                f"SELECT {dim_list}, {agg_expr} AS metric_value "
                f"FROM {self._source_table} "
                f"GROUP BY {dim_list}"
            )
        return (
            f"SELECT {agg_expr} AS metric_value FROM {self._source_table}"
        )

    async def process(self, **_: Any) -> dict[str, Any]:
        """Compute the named metric and return a structured metric record.

        Returns:
            A dict with keys ``metric_name``, ``value``, ``dimensions``,
            and ``computed_at``. When dimension_columns are present, ``value``
            is a list of per-dimension records.
        """
        computed_at = datetime.now(timezone.utc).isoformat()
        rows = await self._pool.fetch_all(self._build_query())
        if self._dimension_columns:
            records = []
            for row in rows:
                dim_vals = dict(
                    zip(self._dimension_columns, row[: len(self._dimension_columns)])
                )
                records.append(
                    {"dimensions": dim_vals, "value": row[-1]}
                )
            return {
                "metric_name": self._metric_name,
                "value": records,
                "dimensions": list(self._dimension_columns),
                "computed_at": computed_at,
            }
        value = rows[0][0] if rows else None
        return {
            "metric_name": self._metric_name,
            "value": value,
            "dimensions": [],
            "computed_at": computed_at,
        }
