"""``StatisticalProfiler`` — per-column statistical summary for a table.

Computes the following statistics for each profiled column:

* min, max, mean, median
* stddev
* p5, p25, p75, p95 percentiles
* cardinality (distinct value count)
* null rate
* top-5 most frequent values with their counts
"""

from __future__ import annotations

import statistics
from typing import Any, Sequence

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.domains.data.identifier_validator import IdentifierValidator
from pirn.nodes.sub_tapestry import SubTapestry


class StatisticalProfiler(SubTapestry):
    """Compute comprehensive per-column statistics for a table."""

    def __init__(
        self,
        *,
        pool: DatabaseConnectionPool,
        monitored_table: str,
        columns: Sequence[str],
        top_n: int = 5,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
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
        self._pool = pool
        self._monitored_table = monitored_table
        self._columns = column_tuple
        self._top_n = top_n
        super().__init__(_config=_config, **kwargs)

    def _percentile(self, sorted_vals: list[float], pct: float) -> float:
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

    async def _profile_column(
        self, column: str, total_rows: int
    ) -> dict[str, Any]:
        all_rows = await self._pool.fetch_all(
            f"SELECT {column} FROM {self._monitored_table}"
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
                )[: self._top_n]
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
            p5 = self._percentile(numeric_sorted, 0.05)
            p25 = self._percentile(numeric_sorted, 0.25)
            p75 = self._percentile(numeric_sorted, 0.75)
            p95 = self._percentile(numeric_sorted, 0.95)
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

    async def process(self, **_: Any) -> dict[str, Any]:
        """Compute per-column statistical profile for all configured columns.

        Returns:
            A dict with keys ``succeeded``, ``monitored_table``,
            ``total_rows``, and ``profiles`` (list of per-column dicts).
        """
        total_rows_result = await self._pool.fetch_all(
            f"SELECT COUNT(*) FROM {self._monitored_table}"
        )
        total_rows = total_rows_result[0][0]
        profiles = []
        for column in self._columns:
            profile = await self._profile_column(column, total_rows)
            profiles.append(profile)
        return {
            "succeeded": True,
            "monitored_table": self._monitored_table,
            "total_rows": total_rows,
            "profiles": profiles,
        }
