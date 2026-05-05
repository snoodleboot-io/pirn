"""``FreshnessCheck`` — fail if a table's max timestamp exceeds the SLA.

Queries the maximum value of a configured timestamp column in the target
table and compares it to the current UTC time. Fails if the data is older
than the caller-supplied ``max_age_seconds`` SLA.

Algorithm:
    1. Receive resolved ``pool``, ``monitored_table``, ``timestamp_column``,
       and ``max_age_seconds`` in ``process()``.
    2. Validate all inputs: pool type, identifier safety, positive integer.
    3. Issue ``SELECT MAX(timestamp_column) FROM monitored_table``.
    4. Raise ``RuntimeError`` if the result is NULL (empty table).
    5. Compute ``age_seconds = now_utc - max_timestamp``.
    6. Return result dict including ``sla_breached`` flag.

Math:
    $age\_seconds = (t_{now} - t_{max})$ in seconds

    $sla\_breached = age\_seconds > max\_age\_seconds$

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
from pirn.domains.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.domains.data.identifier_validator import IdentifierValidator


class FreshnessCheck(Knot):
    """Query max updated_at and fail if data is stale beyond the SLA."""

    def __init__(
        self,
        *,
        pool: Knot | DatabaseConnectionPool,
        monitored_table: Knot | str,
        timestamp_column: Knot | str,
        max_age_seconds: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            pool=pool,
            monitored_table=monitored_table,
            timestamp_column=timestamp_column,
            max_age_seconds=max_age_seconds,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        *,
        pool: Any,
        monitored_table: Any,
        timestamp_column: Any,
        max_age_seconds: Any,
        **_: Any,
    ) -> dict[str, Any]:
        """Query max timestamp and compare against SLA threshold.

        Returns:
            A dict with keys ``succeeded``, ``monitored_table``,
            ``max_timestamp``, ``age_seconds``, ``max_age_seconds``,
            and ``sla_breached``.

        Raises:
            TypeError: When pool is not a DatabaseConnectionPool.
            ValueError: When max_age_seconds is not a positive integer.
            RuntimeError: When max_timestamp is NULL (table is empty).
        """
        if not isinstance(pool, DatabaseConnectionPool):
            raise TypeError(
                "FreshnessCheck: pool must be a DatabaseConnectionPool"
            )
        if not isinstance(monitored_table, str) or not monitored_table:
            raise ValueError(
                "FreshnessCheck: monitored_table must be a non-empty string"
            )
        if not isinstance(timestamp_column, str) or not timestamp_column:
            raise ValueError(
                "FreshnessCheck: timestamp_column must be a non-empty string"
            )
        IdentifierValidator.validate_column("monitored_table", monitored_table)
        IdentifierValidator.validate_column("timestamp_column", timestamp_column)
        if not isinstance(max_age_seconds, int) or max_age_seconds < 1:
            raise ValueError(
                "FreshnessCheck: max_age_seconds must be a positive integer"
            )
        rows = await pool.fetch_all(
            f"SELECT MAX({timestamp_column}) FROM {monitored_table}"
        )
        max_ts_raw = rows[0][0]
        if max_ts_raw is None:
            raise RuntimeError(
                f"FreshnessCheck: {monitored_table}.{timestamp_column} "
                f"returned NULL — table may be empty"
            )
        if isinstance(max_ts_raw, str):
            max_ts = datetime.fromisoformat(max_ts_raw)
            if max_ts.tzinfo is None:
                max_ts = max_ts.replace(tzinfo=UTC)
        elif isinstance(max_ts_raw, datetime):
            max_ts = max_ts_raw
            if max_ts.tzinfo is None:
                max_ts = max_ts.replace(tzinfo=UTC)
        else:
            raise TypeError(
                f"FreshnessCheck: unexpected timestamp type {type(max_ts_raw)}"
            )
        now = datetime.now(UTC)
        age_seconds = (now - max_ts).total_seconds()
        sla_breached = age_seconds > max_age_seconds
        return {
            "succeeded": True,
            "monitored_table": monitored_table,
            "max_timestamp": max_ts.isoformat(),
            "age_seconds": age_seconds,
            "max_age_seconds": max_age_seconds,
            "sla_breached": sla_breached,
        }
