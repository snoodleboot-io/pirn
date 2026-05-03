"""``ReferentialIntegrityCheck`` — FK orphan detection between fact and dimension.

Checks that every FK value in a fact column has a corresponding row in
the referenced dimension table. Reports the count and percentage of
orphaned FK values.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.domains.data.identifier_validator import IdentifierValidator
from pirn.nodes.sub_tapestry import SubTapestry


class ReferentialIntegrityCheck(SubTapestry):
    """Detect orphaned foreign key values in a fact table column."""

    def __init__(
        self,
        *,
        pool: DatabaseConnectionPool,
        fact_table: str,
        fact_column: str,
        dimension_table: str,
        dimension_column: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(pool, DatabaseConnectionPool):
            raise TypeError(
                "ReferentialIntegrityCheck: pool must be a DatabaseConnectionPool"
            )
        IdentifierValidator.validate_column("fact_table", fact_table)
        IdentifierValidator.validate_column("fact_column", fact_column)
        IdentifierValidator.validate_column("dimension_table", dimension_table)
        IdentifierValidator.validate_column(
            "dimension_column", dimension_column
        )
        self._pool = pool
        self._fact_table = fact_table
        self._fact_column = fact_column
        self._dimension_table = dimension_table
        self._dimension_column = dimension_column
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> dict[str, Any]:
        """Count orphaned FK rows and compute orphan percentage.

        Returns:
            A dict with keys ``succeeded``, ``fact_table``,
            ``fact_column``, ``dimension_table``, ``dimension_column``,
            ``total_rows``, ``orphaned_rows``, ``orphaned_pct``,
            and ``has_orphans``.
        """
        total_rows_result = await self._pool.fetch_all(
            f"SELECT COUNT(*) FROM {self._fact_table}"
        )
        total_rows = total_rows_result[0][0]
        orphaned_rows_result = await self._pool.fetch_all(
            f"SELECT COUNT(*) FROM {self._fact_table} f "
            f"WHERE f.{self._fact_column} NOT IN "
            f"(SELECT {self._dimension_column} FROM {self._dimension_table})"
        )
        orphaned_rows = orphaned_rows_result[0][0]
        orphaned_pct = (
            (orphaned_rows / total_rows * 100.0) if total_rows > 0 else 0.0
        )
        return {
            "succeeded": True,
            "fact_table": self._fact_table,
            "fact_column": self._fact_column,
            "dimension_table": self._dimension_table,
            "dimension_column": self._dimension_column,
            "total_rows": total_rows,
            "orphaned_rows": orphaned_rows,
            "orphaned_pct": orphaned_pct,
            "has_orphans": orphaned_rows > 0,
        }
