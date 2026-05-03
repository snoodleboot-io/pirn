"""``ExposureLineageTag`` — writes a lineage record to an audit log table.

Links a source table, transform knot id, and target table by inserting a
record into a lineage audit log table.
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


class ExposureLineageTag(SubTapestry):
    """Write a lineage record linking source table, transform, and target table."""

    def __init__(
        self,
        *,
        pool: DatabaseConnectionPool,
        source_table: str,
        transform_knot_id: str,
        target_table: str,
        audit_log_table: str = "lineage_audit_log",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(pool, DatabaseConnectionPool):
            raise TypeError(
                "ExposureLineageTag: pool must be a DatabaseConnectionPool"
            )
        for label, value in (
            ("source_table", source_table),
            ("transform_knot_id", transform_knot_id),
            ("target_table", target_table),
            ("audit_log_table", audit_log_table),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(
                    f"ExposureLineageTag: {label} must be a non-empty string"
                )
        IdentifierValidator.validate_column("source_table", source_table)
        IdentifierValidator.validate_column("target_table", target_table)
        IdentifierValidator.validate_column("audit_log_table", audit_log_table)
        self._pool = pool
        self._source_table = source_table
        self._transform_knot_id = transform_knot_id
        self._target_table = target_table
        self._audit_log_table = audit_log_table
        super().__init__(_config=_config, **kwargs)

    @property
    def insert_query(self) -> str:
        return (
            f"INSERT INTO {self._audit_log_table} "
            f"(source_table, transform_knot_id, target_table, recorded_at) "
            f"VALUES (?, ?, ?, ?)"
        )

    async def process(self, **_: Any) -> dict[str, Any]:
        """Insert a lineage record into the audit log table.

        Returns:
            A dict with keys ``succeeded``, ``source_table``,
            ``transform_knot_id``, ``target_table``, and ``recorded_at``.
        """
        recorded_at = datetime.now(timezone.utc).isoformat()
        await self._pool.execute(
            self.insert_query,
            (
                self._source_table,
                self._transform_knot_id,
                self._target_table,
                recorded_at,
            ),
        )
        return {
            "succeeded": True,
            "source_table": self._source_table,
            "transform_knot_id": self._transform_knot_id,
            "target_table": self._target_table,
            "recorded_at": recorded_at,
        }
