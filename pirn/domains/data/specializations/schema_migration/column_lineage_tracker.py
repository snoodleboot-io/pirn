"""``ColumnLineageTracker`` — records column-level lineage to a registry table.

Writes source_table.col → transform_id → target_table.col mappings into
a lineage registry table.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Sequence

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.domains.data.identifier_validator import IdentifierValidator
from pirn.nodes.sub_tapestry import SubTapestry


class ColumnLineageTracker(SubTapestry):
    """Record column-level lineage mappings into a lineage registry table."""

    def __init__(
        self,
        *,
        pool: DatabaseConnectionPool,
        source_table: str,
        target_table: str,
        transform_id: str,
        column_mappings: Sequence[tuple[str, str]],
        lineage_table: str = "column_lineage_registry",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(pool, DatabaseConnectionPool):
            raise TypeError(
                "ColumnLineageTracker: pool must be a DatabaseConnectionPool"
            )
        for label, value in (
            ("source_table", source_table),
            ("target_table", target_table),
            ("transform_id", transform_id),
            ("lineage_table", lineage_table),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(
                    f"ColumnLineageTracker: {label} must be a non-empty string"
                )
        if not column_mappings:
            raise ValueError(
                "ColumnLineageTracker: column_mappings must be non-empty"
            )
        IdentifierValidator.validate_column("source_table", source_table)
        IdentifierValidator.validate_column("target_table", target_table)
        IdentifierValidator.validate_column("lineage_table", lineage_table)
        for idx, (src_col, tgt_col) in enumerate(column_mappings):
            IdentifierValidator.validate_column(
                f"column_mappings[{idx}] source", src_col
            )
            IdentifierValidator.validate_column(
                f"column_mappings[{idx}] target", tgt_col
            )
        self._pool = pool
        self._source_table = source_table
        self._target_table = target_table
        self._transform_id = transform_id
        self._column_mappings = list(column_mappings)
        self._lineage_table = lineage_table
        super().__init__(_config=_config, **kwargs)

    @property
    def insert_query(self) -> str:
        return (
            f"INSERT INTO {self._lineage_table} "
            f"(source_table, source_column, transform_id, "
            f"target_table, target_column, recorded_at) "
            f"VALUES (?, ?, ?, ?, ?, ?)"
        )

    async def process(self, **_: Any) -> dict[str, Any]:
        """Write all column-level lineage mappings to the registry table.

        Returns:
            A dict with keys ``succeeded``, ``lineage_table``, and
            ``mappings_recorded`` summarising the lineage write.
        """
        recorded_at = datetime.now(timezone.utc).isoformat()
        for src_col, tgt_col in self._column_mappings:
            await self._pool.execute(
                self.insert_query,
                (
                    self._source_table,
                    src_col,
                    self._transform_id,
                    self._target_table,
                    tgt_col,
                    recorded_at,
                ),
            )
        return {
            "succeeded": True,
            "lineage_table": self._lineage_table,
            "mappings_recorded": len(self._column_mappings),
        }
