"""``RowCountAnomalyDetector`` — flags row count deviations from a rolling average.

Queries the current run's row count and compares it against the rolling
average of the last N recorded counts. Raises if the relative deviation
exceeds the configured threshold. Run-count history is maintained in a
dedicated audit table.

Algorithm:
    1. Receive resolved ``pool``, ``monitored_table``, ``audit_table``,
       ``window``, and ``threshold`` in ``process()``.
    2. Validate all inputs: pool type, identifier safety, positive window and threshold.
    3. Issue ``SELECT COUNT(*) FROM monitored_table`` for current count.
    4. Insert current count into audit_table with UTC timestamp.
    5. Fetch last ``window + 1`` rows from audit_table for this table.
    6. If fewer than 2 rows, return early with no anomaly.
    7. Compute rolling average of prior counts; compute relative deviation.
    8. Return result dict including ``anomaly_detected`` flag.

Math:
    $\\bar{x}_{prior} = \\frac{1}{N} \\sum_{i=1}^{N} count_i$

    $deviation = \\frac{|count_{current} - \\bar{x}_{prior}|}{\\bar{x}_{prior}}$

    $anomaly\\_detected = deviation > threshold$

References:
    [1] pirn — DatabaseConnectionPool interface:
        pirn/domains/connectors/database_connection_pool.py
    [2] pirn — IdentifierValidator (SQL injection guard):
        pirn/domains/data/identifier_validator.py
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pirn.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.identifier_validator import IdentifierValidator


class RowCountAnomalyDetector(Knot):
    """Compare current run row count against rolling average; flag anomalies."""

    def __init__(
        self,
        *,
        pool: Knot | DatabaseConnectionPool,
        monitored_table: Knot | str,
        audit_table: Knot | str,
        window: Knot | int = 7,
        threshold: Knot | float = 0.30,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            pool=pool,
            monitored_table=monitored_table,
            audit_table=audit_table,
            window=window,
            threshold=threshold,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        *,
        pool: Any,
        monitored_table: Any,
        audit_table: Any,
        window: Any,
        threshold: Any,
        **_: Any,
    ) -> dict[str, Any]:
        """Count monitored table rows, record in audit, flag if anomalous.

        Returns:
            A dict with keys ``succeeded``, ``monitored_table``,
            ``current_count``, ``rolling_avg``, ``deviation``,
            ``threshold``, and ``anomaly_detected``.

        Raises:
            TypeError: When pool is not a DatabaseConnectionPool.
            ValueError: When window or threshold are invalid.
        """
        if not isinstance(pool, DatabaseConnectionPool):
            raise TypeError("RowCountAnomalyDetector: pool must be a DatabaseConnectionPool")
        IdentifierValidator.validate_column("monitored_table", monitored_table)
        IdentifierValidator.validate_column("audit_table", audit_table)
        if not isinstance(window, int) or window < 1:
            raise ValueError("RowCountAnomalyDetector: window must be a positive integer")
        if not isinstance(threshold, (int, float)) or threshold <= 0:
            raise ValueError("RowCountAnomalyDetector: threshold must be a positive number")
        threshold_f = float(threshold)
        count_rows = await pool.fetch_all(f"SELECT COUNT(*) FROM {monitored_table}")
        current_count = count_rows[0][0]
        now_iso = datetime.now(UTC).isoformat()
        await pool.execute(
            f"INSERT INTO {audit_table} (table_name, row_count, recorded_at) VALUES (?, ?, ?)",
            (monitored_table, current_count, now_iso),
        )
        history_rows = await pool.fetch_all(
            f"SELECT row_count FROM {audit_table} "
            f"WHERE table_name = ? "
            f"ORDER BY recorded_at DESC LIMIT ?",
            (monitored_table, window + 1),
        )
        counts = [r[0] for r in history_rows]
        if len(counts) < 2:
            return {
                "succeeded": True,
                "monitored_table": monitored_table,
                "current_count": current_count,
                "rolling_avg": None,
                "deviation": None,
                "threshold": threshold_f,
                "anomaly_detected": False,
            }
        prior_counts = counts[1:]
        rolling_avg = sum(prior_counts) / len(prior_counts)
        if rolling_avg == 0:
            deviation = 0.0
        else:
            deviation = abs(current_count - rolling_avg) / rolling_avg
        anomaly_detected = deviation > threshold_f
        return {
            "succeeded": True,
            "monitored_table": monitored_table,
            "current_count": current_count,
            "rolling_avg": rolling_avg,
            "deviation": deviation,
            "threshold": threshold_f,
            "anomaly_detected": anomaly_detected,
        }
