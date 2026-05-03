"""``FreshnessCheck`` — fail if a table's max timestamp exceeds the SLA.

Queries the maximum value of a configured timestamp column in the target
table and compares it to the current UTC time. Fails if the data is older
than the caller-supplied ``max_age_seconds`` SLA.
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


class FreshnessCheck(SubTapestry):
    """Query max updated_at and fail if data is stale beyond the SLA."""

    def __init__(
        self,
        *,
        pool: DatabaseConnectionPool,
        monitored_table: str,
        timestamp_column: str,
        max_age_seconds: int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(pool, DatabaseConnectionPool):
            raise TypeError(
                "FreshnessCheck: pool must be a DatabaseConnectionPool"
            )
        IdentifierValidator.validate_column("monitored_table", monitored_table)
        IdentifierValidator.validate_column("timestamp_column", timestamp_column)
        if not isinstance(max_age_seconds, int) or max_age_seconds < 1:
            raise ValueError(
                "FreshnessCheck: max_age_seconds must be a positive integer"
            )
        self._pool = pool
        self._monitored_table = monitored_table
        self._timestamp_column = timestamp_column
        self._max_age_seconds = max_age_seconds
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> dict[str, Any]:
        """Query max timestamp and compare against SLA threshold.

        Returns:
            A dict with keys ``succeeded``, ``monitored_table``,
            ``max_timestamp``, ``age_seconds``, ``max_age_seconds``,
            and ``sla_breached``.

        Raises:
            RuntimeError: When max_timestamp is NULL (table is empty).
        """
        rows = await self._pool.fetch_all(
            f"SELECT MAX({self._timestamp_column}) FROM {self._monitored_table}"
        )
        max_ts_raw = rows[0][0]
        if max_ts_raw is None:
            raise RuntimeError(
                f"FreshnessCheck: {self._monitored_table}.{self._timestamp_column} "
                f"returned NULL — table may be empty"
            )
        if isinstance(max_ts_raw, str):
            max_ts = datetime.fromisoformat(max_ts_raw)
            if max_ts.tzinfo is None:
                max_ts = max_ts.replace(tzinfo=timezone.utc)
        elif isinstance(max_ts_raw, datetime):
            max_ts = max_ts_raw
            if max_ts.tzinfo is None:
                max_ts = max_ts.replace(tzinfo=timezone.utc)
        else:
            raise TypeError(
                f"FreshnessCheck: unexpected timestamp type {type(max_ts_raw)}"
            )
        now = datetime.now(timezone.utc)
        age_seconds = (now - max_ts).total_seconds()
        sla_breached = age_seconds > self._max_age_seconds
        return {
            "succeeded": True,
            "monitored_table": self._monitored_table,
            "max_timestamp": max_ts.isoformat(),
            "age_seconds": age_seconds,
            "max_age_seconds": self._max_age_seconds,
            "sla_breached": sla_breached,
        }
