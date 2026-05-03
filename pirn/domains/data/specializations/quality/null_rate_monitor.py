"""``NullRateMonitor`` — per-column null rate check against configurable thresholds.

Computes the fraction of NULL values for each monitored column and
compares against caller-supplied per-column thresholds. All violations
are collected and returned in the result; the knot does not short-circuit
on the first violation.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.domains.data.identifier_validator import IdentifierValidator
from pirn.nodes.sub_tapestry import SubTapestry


class NullRateMonitor(SubTapestry):
    """Compute per-column null rates and report threshold violations."""

    def __init__(
        self,
        *,
        pool: DatabaseConnectionPool,
        monitored_table: str,
        column_thresholds: dict[str, float],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(pool, DatabaseConnectionPool):
            raise TypeError(
                "NullRateMonitor: pool must be a DatabaseConnectionPool"
            )
        IdentifierValidator.validate_column("monitored_table", monitored_table)
        if not column_thresholds:
            raise ValueError(
                "NullRateMonitor: column_thresholds must be non-empty"
            )
        for col in column_thresholds:
            IdentifierValidator.validate_column("column_thresholds key", col)
        self._pool = pool
        self._monitored_table = monitored_table
        self._column_thresholds = dict(column_thresholds)
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> dict[str, Any]:
        """Measure null rates per column and return all threshold violations.

        Returns:
            A dict with keys ``succeeded``, ``monitored_table``,
            ``null_rates``, and ``violations``.
        """
        total_rows_result = await self._pool.fetch_all(
            f"SELECT COUNT(*) FROM {self._monitored_table}"
        )
        total_rows = total_rows_result[0][0]
        null_rates: dict[str, float] = {}
        violations: list[dict[str, Any]] = []
        for column, threshold in self._column_thresholds.items():
            if total_rows == 0:
                null_rate = 0.0
            else:
                null_count_result = await self._pool.fetch_all(
                    f"SELECT COUNT(*) FROM {self._monitored_table} "
                    f"WHERE {column} IS NULL"
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
            "monitored_table": self._monitored_table,
            "null_rates": null_rates,
            "violations": violations,
        }
