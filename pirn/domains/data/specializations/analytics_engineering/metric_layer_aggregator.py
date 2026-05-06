"""``MetricLayerAggregator`` — computes a named metric with optional dimension slicing.

Supports sum, count, avg, and ratio aggregations. Returns a structured
metric record with name, value, dimensions, and computed_at timestamp.

Algorithm:
    1. Receive resolved ``pool``, ``source_table``, ``metric_name``,
       ``aggregation``, ``value_column``, ``dimension_columns``,
       ``numerator_column``, and ``denominator_column`` in ``process()``.
    2. Validate all inputs: pool type, non-empty strings, allowed aggregation,
       identifier safety, and ratio-specific column requirements.
    3. Build and execute the aggregation SQL against ``pool``.
    4. Return a structured metric record. When ``dimension_columns`` are
       present, ``value`` is a list of per-dimension dicts; otherwise a scalar.

References:
    [1] pirn — DatabaseConnectionPool interface:
        pirn/domains/connectors/database_connection_pool.py
    [2] pirn — IdentifierValidator (SQL injection guard):
        pirn/domains/data/identifier_validator.py
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.data.identifier_validator import IdentifierValidator

_SUPPORTED_AGGREGATIONS: frozenset[str] = frozenset({"sum", "count", "avg", "ratio"})


class MetricLayerAggregator(Knot):
    """Compute a named metric (sum/count/avg/ratio) with optional dimension slicing."""

    def __init__(
        self,
        *,
        pool: Knot | DatabaseConnectionPool,
        source_table: Knot | str,
        metric_name: Knot | str,
        aggregation: Knot | str,
        value_column: Knot | str,
        dimension_columns: Knot | tuple[str, ...] = (),
        numerator_column: Knot | str = "",
        denominator_column: Knot | str = "",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            pool=pool,
            source_table=source_table,
            metric_name=metric_name,
            aggregation=aggregation,
            value_column=value_column,
            dimension_columns=dimension_columns,
            numerator_column=numerator_column,
            denominator_column=denominator_column,
            _config=_config,
            **kwargs,
        )

    @staticmethod
    def _build_query(
        source_table: str,
        aggregation: str,
        value_column: str,
        dimension_columns: tuple[str, ...],
        numerator_column: str,
        denominator_column: str,
    ) -> str:
        if aggregation == "sum":
            agg_expr = f"SUM({value_column})"
        elif aggregation == "count":
            agg_expr = f"COUNT({value_column})"
        elif aggregation == "avg":
            agg_expr = f"AVG({value_column})"
        else:
            agg_expr = (
                f"CAST(SUM({numerator_column}) AS REAL) / NULLIF(SUM({denominator_column}), 0)"
            )
        if dimension_columns:
            dim_list = ", ".join(dimension_columns)
            return (
                f"SELECT {dim_list}, {agg_expr} AS metric_value "
                f"FROM {source_table} "
                f"GROUP BY {dim_list}"
            )
        return f"SELECT {agg_expr} AS metric_value FROM {source_table}"

    async def process(
        self,
        *,
        pool: Any,
        source_table: Any,
        metric_name: Any,
        aggregation: Any,
        value_column: Any,
        dimension_columns: Any = (),
        numerator_column: Any = "",
        denominator_column: Any = "",
        **_: Any,
    ) -> dict[str, Any]:
        if not isinstance(pool, DatabaseConnectionPool):
            raise TypeError("MetricLayerAggregator: pool must be a DatabaseConnectionPool")
        for label, value in (
            ("source_table", source_table),
            ("metric_name", metric_name),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(f"MetricLayerAggregator: {label} must be a non-empty string")
        if aggregation not in _SUPPORTED_AGGREGATIONS:
            raise ValueError(
                f"MetricLayerAggregator: aggregation must be one of "
                f"{sorted(_SUPPORTED_AGGREGATIONS)!r}, got {aggregation!r}"
            )
        IdentifierValidator.validate_column("source_table", source_table)
        if aggregation == "ratio":
            if not numerator_column or not denominator_column:
                raise ValueError(
                    "MetricLayerAggregator: ratio aggregation requires "
                    "numerator_column and denominator_column"
                )
            IdentifierValidator.validate_column("numerator_column", numerator_column)
            IdentifierValidator.validate_column("denominator_column", denominator_column)
        else:
            IdentifierValidator.validate_column("value_column", value_column)
        dim_tuple = tuple(dimension_columns)
        if dim_tuple:
            IdentifierValidator.validate_columns("dimension_columns", dim_tuple)
        computed_at = datetime.now(UTC).isoformat()
        rows = await pool.fetch_all(
            MetricLayerAggregator._build_query(
                source_table,
                aggregation,
                value_column,
                dim_tuple,
                numerator_column,
                denominator_column,
            )
        )
        if dim_tuple:
            records = []
            for row in rows:
                dim_vals = dict(zip(dim_tuple, row[: len(dim_tuple)], strict=False))
                records.append({"dimensions": dim_vals, "value": row[-1]})
            return {
                "metric_name": metric_name,
                "value": records,
                "dimensions": list(dim_tuple),
                "computed_at": computed_at,
            }
        value = rows[0][0] if rows else None
        return {
            "metric_name": metric_name,
            "value": value,
            "dimensions": [],
            "computed_at": computed_at,
        }
