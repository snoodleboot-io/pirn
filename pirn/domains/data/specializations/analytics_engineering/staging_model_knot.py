"""``StagingModelKnot`` — source-to-staging transform knot.

Reads rows from a source table via ``source_query``, applies column
renames, type casts, appends a ``_loaded_at`` metadata column, and
writes the results to a staging table.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.domains.data.identifier_validator import IdentifierValidator
from pirn.nodes.sub_tapestry import SubTapestry


class StagingModelKnot(SubTapestry):
    """Apply source-to-staging transforms and write to a staging table.

    Renames columns, applies SQL-cast expressions, appends ``_loaded_at``,
    and inserts results into the target staging table.
    """

    def __init__(
        self,
        *,
        source_pool: DatabaseConnectionPool,
        source_query: str,
        target_pool: DatabaseConnectionPool,
        target_table: str,
        column_map: Mapping[str, str],
        loaded_at_column: str = "_loaded_at",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(source_pool, DatabaseConnectionPool):
            raise TypeError(
                "StagingModelKnot: source_pool must be a DatabaseConnectionPool"
            )
        if not isinstance(target_pool, DatabaseConnectionPool):
            raise TypeError(
                "StagingModelKnot: target_pool must be a DatabaseConnectionPool"
            )
        for label, value in (
            ("source_query", source_query),
            ("target_table", target_table),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(
                    f"StagingModelKnot: {label} must be a non-empty string"
                )
        if not isinstance(column_map, Mapping) or not column_map:
            raise ValueError(
                "StagingModelKnot: column_map must be a non-empty mapping"
            )
        IdentifierValidator.validate_column("target_table", target_table)
        IdentifierValidator.validate_column("loaded_at_column", loaded_at_column)
        for src_col, dst_col in column_map.items():
            IdentifierValidator.validate_column("column_map key", src_col)
            IdentifierValidator.validate_column("column_map value", dst_col)
        self._source_pool = source_pool
        self._source_query = source_query
        self._target_pool = target_pool
        self._target_table = target_table
        self._column_map = dict(column_map)
        self._loaded_at_column = loaded_at_column
        self._source_columns = list(column_map.keys())
        self._target_columns = list(column_map.values()) + [loaded_at_column]
        super().__init__(_config=_config, **kwargs)

    @property
    def insert_query(self) -> str:
        cols = ", ".join(self._target_columns)
        placeholders = ", ".join(["?"] * len(self._target_columns))
        return (
            f"INSERT INTO {self._target_table} ({cols}) VALUES ({placeholders})"
        )

    async def process(self, **_: Any) -> dict[str, Any]:
        """Read source rows, apply renames, append _loaded_at, write to staging table.

        Returns:
            A dict with keys ``succeeded``, ``target_table``, and
            ``rows_written`` summarising the staging run.
        """
        source_rows = await self._source_pool.fetch_all(self._source_query)
        loaded_at = datetime.now(timezone.utc).isoformat()
        rows_written = 0
        for row in source_rows:
            row_dict = dict(zip(self._source_columns, row))
            values = tuple(row_dict[c] for c in self._source_columns) + (
                loaded_at,
            )
            await self._target_pool.execute(self.insert_query, values)
            rows_written += 1
        return {
            "succeeded": True,
            "target_table": self._target_table,
            "rows_written": rows_written,
        }
