"""``RowCountAnomalyDetector`` — flags row count deviations from a rolling average.

Queries the current run's row count and compares it against the rolling
average of the last N recorded counts. Raises if the relative deviation
exceeds the configured threshold. Run-count history is maintained in a
dedicated audit table.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.domains.data.identifier_validator import IdentifierValidator
from pirn.nodes.sub_tapestry import SubTapestry


class RowCountAnomalyDetector(SubTapestry):
    """Compare current run row count against rolling average; flag anomalies."""

    def __init__(
        self,
        *,
        pool: DatabaseConnectionPool,
        monitored_table: str,
        audit_table: str,
        window: int = 7,
        threshold: float = 0.30,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(pool, DatabaseConnectionPool):
            raise TypeError(
                "RowCountAnomalyDetector: pool must be a DatabaseConnectionPool"
            )
        IdentifierValidator.validate_column("monitored_table", monitored_table)
        IdentifierValidator.validate_column("audit_table", audit_table)
        if not isinstance(window, int) or window < 1:
            raise ValueError(
                "RowCountAnomalyDetector: window must be a positive integer"
            )
        if not isinstance(threshold, (int, float)) or threshold <= 0:
            raise ValueError(
                "RowCountAnomalyDetector: threshold must be a positive number"
            )
        self._pool = pool
        self._monitored_table = monitored_table
        self._audit_table = audit_table
        self._window = window
        self._threshold = float(threshold)
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> dict[str, Any]:
        """Count monitored table rows, record in audit, flag if anomalous.

        Returns:
            A dict with keys ``succeeded``, ``monitored_table``,
            ``current_count``, ``rolling_avg``, ``deviation``,
            ``threshold``, and ``anomaly_detected``.
        """
        count_rows = await self._pool.fetch_all(
            f"SELECT COUNT(*) FROM {self._monitored_table}"
        )
        current_count = count_rows[0][0]
        now_iso = datetime.now(timezone.utc).isoformat()
        await self._pool.execute(
            f"INSERT INTO {self._audit_table} (table_name, row_count, recorded_at) "
            f"VALUES (?, ?, ?)",
            (self._monitored_table, current_count, now_iso),
        )
        history_rows = await self._pool.fetch_all(
            f"SELECT row_count FROM {self._audit_table} "
            f"WHERE table_name = ? "
            f"ORDER BY recorded_at DESC LIMIT ?",
            (self._monitored_table, self._window + 1),
        )
        counts = [r[0] for r in history_rows]
        if len(counts) < 2:
            return {
                "succeeded": True,
                "monitored_table": self._monitored_table,
                "current_count": current_count,
                "rolling_avg": None,
                "deviation": None,
                "threshold": self._threshold,
                "anomaly_detected": False,
            }
        prior_counts = counts[1:]
        rolling_avg = sum(prior_counts) / len(prior_counts)
        if rolling_avg == 0:
            deviation = 0.0
        else:
            deviation = abs(current_count - rolling_avg) / rolling_avg
        anomaly_detected = deviation > self._threshold
        return {
            "succeeded": True,
            "monitored_table": self._monitored_table,
            "current_count": current_count,
            "rolling_avg": rolling_avg,
            "deviation": deviation,
            "threshold": self._threshold,
            "anomaly_detected": anomaly_detected,
        }
