"""``ColumnLineageTracker`` — records column-level lineage to a registry table.

Writes source_table.col → transform_id → target_table.col mappings into
a lineage registry table.

Algorithm:
    1. Receive resolved ``pool``, ``source_table``, ``target_table``,
       ``transform_id``, ``column_mappings``, and ``lineage_table`` in
       ``process()``.
    2. Validate pool type, non-empty strings, identifier safety, and
       non-empty column_mappings.
    3. For each ``(src_col, tgt_col)`` pair, INSERT a row into
       ``lineage_table`` with the current UTC timestamp.
    4. Return a summary dict with ``succeeded``, ``lineage_table``, and
       ``mappings_recorded``.

References:
    [1] pirn — DatabaseConnectionPool interface:
        pirn/domains/connectors/database_connection_pool.py
    [2] pirn — IdentifierValidator (SQL injection guard):
        pirn/domains/data/identifier_validator.py
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.data.identifier_validator import IdentifierValidator


class ColumnLineageTracker(Knot):
    """Record column-level lineage mappings into a lineage registry table."""

    def __init__(
        self,
        *,
        pool: Knot | DatabaseConnectionPool,
        source_table: Knot | str,
        target_table: Knot | str,
        transform_id: Knot | str,
        column_mappings: Knot | Sequence[tuple[str, str]],
        lineage_table: Knot | str = "column_lineage_registry",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            pool=pool,
            source_table=source_table,
            target_table=target_table,
            transform_id=transform_id,
            column_mappings=column_mappings,
            lineage_table=lineage_table,
            _config=_config,
            **kwargs,
        )

    @staticmethod
    def _insert_query(lineage_table: str) -> str:
        return (
            f"INSERT INTO {lineage_table} "
            f"(source_table, source_column, transform_id, "
            f"target_table, target_column, recorded_at) "
            f"VALUES (?, ?, ?, ?, ?, ?)"
        )

    async def process(
        self,
        *,
        pool: Any,
        source_table: Any,
        target_table: Any,
        transform_id: Any,
        column_mappings: Any,
        lineage_table: Any = "column_lineage_registry",
        **_: Any,
    ) -> dict[str, Any]:
        """Write all column-level lineage mappings to the registry table.

        Args:
            pool: DatabaseConnectionPool to write lineage records to.
            source_table: Name of the source table.
            target_table: Name of the target table.
            transform_id: Identifier for the transform producing this lineage.
            column_mappings: Sequence of (source_col, target_col) pairs.
            lineage_table: Registry table name.

        Returns:
            A dict with keys ``succeeded``, ``lineage_table``, and
            ``mappings_recorded`` summarising the lineage write.
        """
        if not isinstance(pool, DatabaseConnectionPool):
            raise TypeError("ColumnLineageTracker: pool must be a DatabaseConnectionPool")
        for label, value in (
            ("source_table", source_table),
            ("target_table", target_table),
            ("transform_id", transform_id),
            ("lineage_table", lineage_table),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(f"ColumnLineageTracker: {label} must be a non-empty string")
        if not column_mappings:
            raise ValueError("ColumnLineageTracker: column_mappings must be non-empty")
        IdentifierValidator.validate_column("source_table", source_table)
        IdentifierValidator.validate_column("target_table", target_table)
        IdentifierValidator.validate_column("lineage_table", lineage_table)
        mappings = list(column_mappings)
        for idx, (src_col, tgt_col) in enumerate(mappings):
            IdentifierValidator.validate_column(f"column_mappings[{idx}] source", src_col)
            IdentifierValidator.validate_column(f"column_mappings[{idx}] target", tgt_col)

        recorded_at = datetime.now(UTC).isoformat()
        for src_col, tgt_col in mappings:
            await pool.execute(
                ColumnLineageTracker._insert_query(lineage_table),
                (source_table, src_col, transform_id, target_table, tgt_col, recorded_at),
            )
        return {
            "succeeded": True,
            "lineage_table": lineage_table,
            "mappings_recorded": len(mappings),
        }
