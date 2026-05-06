"""``StatisticalProfiler`` — per-column statistical summary for a table.

Computes the following statistics for each profiled column:

* min, max, mean, median
* stddev
* p5, p25, p75, p95 percentiles
* cardinality (distinct value count)
* null rate
* top-N most frequent values with their counts

Algorithm:
    1. Receive resolved ``pool``, ``monitored_table``, ``columns``, and
       ``top_n`` in ``process()``.
    2. Validate all inputs: pool type, identifier safety, non-empty columns,
       positive top_n.
    3. Issue ``SELECT COUNT(*) FROM monitored_table``.
    4. For each column, fetch all values; compute null rate, cardinality,
       top-N frequencies, and numeric statistics.
    5. Return result dict with ``profiles`` list.

Math:
    $null\\_rate_c = \\frac{COUNT(c \\text{ IS NULL})}{COUNT(*)}$

    $p_q = x_{\\lfloor (N-1) q \\rfloor}
    + \\text{frac} \\cdot (x_{\\lceil (N-1) q \\rceil} - x_{\\lfloor (N-1) q \\rfloor})$

References:
    [1] pirn — DatabaseConnectionPool interface:
        pirn/domains/connectors/database_connection_pool.py
    [2] pirn — IdentifierValidator (SQL injection guard):
        pirn/domains/data/identifier_validator.py
"""

from __future__ import annotations

import statistics
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.domains.data.identifier_validator import IdentifierValidator


class StatisticalProfiler(Knot):
    """Compute comprehensive per-column statistics for a table."""

    def __init__(
        self,
        *,
        pool: Knot | DatabaseConnectionPool,
        monitored_table: Knot | str,
        columns: Knot | tuple[str, ...],
        top_n: Knot | int = 5,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            pool=pool,
            monitored_table=monitored_table,
            columns=columns,
            top_n=top_n,
            _config=_config,
            **kwargs,
        )

    @staticmethod
    def _percentile(sorted_vals: list[float], pct: float) -> float:
        if not sorted_vals:
            return 0.0
        idx = (len(sorted_vals) - 1) * pct
        lower = int(idx)
        upper = lower + 1
        if upper >= len(sorted_vals):
            return float(sorted_vals[lower])
        frac = idx - lower
        return float(sorted_vals[lower]) + frac * (
            float(sorted_vals[upper]) - float(sorted_vals[lower])
        )

    @staticmethod
    async def _profile_column(
        pool: DatabaseConnectionPool,
        column: str,
        monitored_table: str,
        total_rows: int,
        top_n: int,
    ) -> dict[str, Any]:
        all_rows = await pool.fetch_all(
            f"SELECT {column} FROM {monitored_table}"
        )
        all_values = [r[0] for r in all_rows]
        null_count = sum(1 for v in all_values if v is None)
        null_rate = null_count / total_rows if total_rows > 0 else 0.0
        non_null = [v for v in all_values if v is not None]
        cardinality = len(set(non_null))
        top_values: list[dict[str, Any]] = []
        if non_null:
            freq: dict[Any, int] = {}
            for v in non_null:
                freq[v] = freq.get(v, 0) + 1
            top_values = [
                {"value": v, "count": c}
                for v, c in sorted(
                    freq.items(), key=lambda x: x[1], reverse=True
                )[:top_n]
            ]
        numeric_vals: list[float] = []
        for v in non_null:
            try:
                numeric_vals.append(float(v))
            except (TypeError, ValueError):
                pass
        if numeric_vals:
            numeric_sorted = sorted(numeric_vals)
            col_min = numeric_sorted[0]
            col_max = numeric_sorted[-1]
            col_mean = statistics.mean(numeric_vals)
            col_median = statistics.median(numeric_vals)
            col_stddev = (
                statistics.stdev(numeric_vals) if len(numeric_vals) > 1 else 0.0
            )
            p5 = StatisticalProfiler._percentile(numeric_sorted, 0.05)
            p25 = StatisticalProfiler._percentile(numeric_sorted, 0.25)
            p75 = StatisticalProfiler._percentile(numeric_sorted, 0.75)
            p95 = StatisticalProfiler._percentile(numeric_sorted, 0.95)
        else:
            col_min = col_max = col_mean = col_median = col_stddev = None
            p5 = p25 = p75 = p95 = None
        return {
            "column": column,
            "min": col_min,
            "max": col_max,
            "mean": col_mean,
            "median": col_median,
            "stddev": col_stddev,
            "p5": p5,
            "p25": p25,
            "p75": p75,
            "p95": p95,
            "cardinality": cardinality,
            "null_rate": null_rate,
            "top_values": top_values,
        }

    async def process(
        self,
        *,
        pool: Any,
        monitored_table: Any,
        columns: Any,
        top_n: Any,
        **_: Any,
    ) -> dict[str, Any]:
        """Compute per-column statistical profile for all configured columns.

        Returns:
            A dict with keys ``succeeded``, ``monitored_table``,
            ``total_rows``, and ``profiles`` (list of per-column dicts).

        Raises:
            TypeError: When pool is not a DatabaseConnectionPool.
            ValueError: When columns is empty or top_n is not a positive integer.
        """
        if not isinstance(pool, DatabaseConnectionPool):
            raise TypeError(
                "StatisticalProfiler: pool must be a DatabaseConnectionPool"
            )
        IdentifierValidator.validate_column("monitored_table", monitored_table)
        column_tuple = tuple(columns)
        IdentifierValidator.validate_columns("columns", column_tuple)
        if not isinstance(top_n, int) or top_n < 1:
            raise ValueError(
                "StatisticalProfiler: top_n must be a positive integer"
            )
        total_rows_result = await pool.fetch_all(
            f"SELECT COUNT(*) FROM {monitored_table}"
        )
        total_rows = total_rows_result[0][0]
        profiles = []
        for column in column_tuple:
            profile = await StatisticalProfiler._profile_column(
                pool, column, monitored_table, total_rows, top_n
            )
            profiles.append(profile)
        return {
            "succeeded": True,
            "monitored_table": monitored_table,
            "total_rows": total_rows,
            "profiles": profiles,
        }
