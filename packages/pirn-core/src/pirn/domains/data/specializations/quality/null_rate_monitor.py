"""``NullRateMonitor`` — per-column null rate check against configurable thresholds.

Computes the fraction of NULL values for each monitored column and
compares against caller-supplied per-column thresholds. All violations
are collected and returned in the result; the knot does not short-circuit
on the first violation.

Algorithm:
    1. Receive resolved ``pool``, ``monitored_table``, and
       ``column_thresholds`` in ``process()``.
    2. Validate all inputs: pool type, identifier, non-empty thresholds.
    3. Issue ``SELECT COUNT(*) FROM monitored_table`` to get total rows.
    4. For each column, issue ``SELECT COUNT(*) FROM monitored_table WHERE
       column IS NULL`` and compute null rate.
    5. Collect all columns where null rate exceeds threshold.
    6. Return result dict with all null rates and violations.

Math:
    $null\\_rate_c = \\frac{COUNT(c \\text{ IS NULL})}{COUNT(*)}$

    $violated_c = null\\_rate_c > threshold_c$

References:
    [1] pirn — DatabaseConnectionPool interface:
        pirn/domains/connectors/database_connection_pool.py
    [2] pirn — IdentifierValidator (SQL injection guard):
        pirn/domains/data/identifier_validator.py
"""

from __future__ import annotations

from typing import Any

from pirn.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.identifier_validator import IdentifierValidator


class NullRateMonitor(Knot):
    """Compute per-column null rates and report threshold violations."""

    def __init__(
        self,
        *,
        pool: Knot | DatabaseConnectionPool,
        monitored_table: Knot | str,
        column_thresholds: Knot | dict[str, float],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            pool=pool,
            monitored_table=monitored_table,
            column_thresholds=column_thresholds,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        *,
        pool: Any,
        monitored_table: Any,
        column_thresholds: Any,
        **_: Any,
    ) -> dict[str, Any]:
        """Measure null rates per column and return all threshold violations.

        Returns:
            A dict with keys ``succeeded``, ``monitored_table``,
            ``null_rates``, and ``violations``.

        Raises:
            TypeError: When pool is not a DatabaseConnectionPool.
            ValueError: When column_thresholds is empty.
        """
        if not isinstance(pool, DatabaseConnectionPool):
            raise TypeError("NullRateMonitor: pool must be a DatabaseConnectionPool")
        if not isinstance(monitored_table, str) or not monitored_table:
            raise ValueError("NullRateMonitor: monitored_table must be a non-empty string")
        IdentifierValidator.validate_column("monitored_table", monitored_table)
        if not column_thresholds:
            raise ValueError("NullRateMonitor: column_thresholds must be non-empty")
        for col in column_thresholds:
            IdentifierValidator.validate_column("column_thresholds key", col)
        total_rows_result = await pool.fetch_all(f"SELECT COUNT(*) FROM {monitored_table}")
        total_rows = total_rows_result[0][0]
        null_rates: dict[str, float] = {}
        violations: list[dict[str, Any]] = []
        for column, threshold in column_thresholds.items():
            if total_rows == 0:
                null_rate = 0.0
            else:
                null_count_result = await pool.fetch_all(
                    f"SELECT COUNT(*) FROM {monitored_table} WHERE {column} IS NULL"
                )
                null_count = null_count_result[0][0]
                null_rate = null_count / total_rows
            null_rates[column] = null_rate
            if null_rate > threshold:
                violations.append(
                    {
                        "column": column,
                        "null_rate": null_rate,
                        "threshold": threshold,
                    }
                )
        return {
            "succeeded": True,
            "monitored_table": monitored_table,
            "null_rates": null_rates,
            "violations": violations,
        }
