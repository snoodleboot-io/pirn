"""``ExposureLineageTag`` — writes a lineage record to an audit log table.

Links a source table, transform knot id, and target table by inserting a
record into a lineage audit log table.

Algorithm:
    1. Receive resolved ``pool``, ``source_table``, ``transform_knot_id``,
       ``target_table``, and ``audit_log_table`` in ``process()``.
    2. Validate all inputs: pool type, non-empty strings, identifier safety.
    3. Capture the current UTC timestamp as ``recorded_at``.
    4. Execute an INSERT into ``audit_log_table`` with all four values.
    5. Return a summary dict with ``succeeded``, ``source_table``,
       ``transform_knot_id``, ``target_table``, and ``recorded_at``.

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


class ExposureLineageTag(Knot):
    """Write a lineage record linking source table, transform, and target table."""

    def __init__(
        self,
        *,
        pool: Knot | DatabaseConnectionPool,
        source_table: Knot | str,
        transform_knot_id: Knot | str,
        target_table: Knot | str,
        audit_log_table: Knot | str = "lineage_audit_log",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            pool=pool,
            source_table=source_table,
            transform_knot_id=transform_knot_id,
            target_table=target_table,
            audit_log_table=audit_log_table,
            _config=_config,
            **kwargs,
        )

    @staticmethod
    def _insert_query(audit_log_table: str) -> str:
        return (
            f"INSERT INTO {audit_log_table} "
            f"(source_table, transform_knot_id, target_table, recorded_at) "
            f"VALUES (?, ?, ?, ?)"
        )

    async def process(
        self,
        *,
        pool: Any,
        source_table: Any,
        transform_knot_id: Any,
        target_table: Any,
        audit_log_table: Any = "lineage_audit_log",
        **_: Any,
    ) -> dict[str, Any]:
        if not isinstance(pool, DatabaseConnectionPool):
            raise TypeError("ExposureLineageTag: pool must be a DatabaseConnectionPool")
        for label, value in (
            ("source_table", source_table),
            ("transform_knot_id", transform_knot_id),
            ("target_table", target_table),
            ("audit_log_table", audit_log_table),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(f"ExposureLineageTag: {label} must be a non-empty string")
        IdentifierValidator.validate_column("source_table", source_table)
        IdentifierValidator.validate_column("target_table", target_table)
        IdentifierValidator.validate_column("audit_log_table", audit_log_table)
        recorded_at = datetime.now(UTC).isoformat()
        await pool.execute(
            ExposureLineageTag._insert_query(audit_log_table),
            (source_table, transform_knot_id, target_table, recorded_at),
        )
        return {
            "succeeded": True,
            "source_table": source_table,
            "transform_knot_id": transform_knot_id,
            "target_table": target_table,
            "recorded_at": recorded_at,
        }
