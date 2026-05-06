"""``ReferentialIntegrityCheck`` — FK orphan detection between fact and dimension.

Checks that every FK value in a fact column has a corresponding row in
the referenced dimension table. Reports the count and percentage of
orphaned FK values.

Algorithm:
    1. Receive resolved ``pool``, ``fact_table``, ``fact_column``,
       ``dimension_table``, and ``dimension_column`` in ``process()``.
    2. Validate all inputs: pool type, identifier safety for all names.
    3. Issue ``SELECT COUNT(*) FROM fact_table`` for total row count.
    4. Issue a NOT IN subquery to count orphaned FK rows.
    5. Compute orphan percentage and return result dict.

Math:
    $orphaned\\_pct = \\frac{orphaned\\_rows}{total\\_rows} \\times 100$

References:
    [1] pirn — DatabaseConnectionPool interface:
        pirn/domains/connectors/database_connection_pool.py
    [2] pirn — IdentifierValidator (SQL injection guard):
        pirn/domains/data/identifier_validator.py
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.domains.data.identifier_validator import IdentifierValidator


class ReferentialIntegrityCheck(Knot):
    """Detect orphaned foreign key values in a fact table column."""

    def __init__(
        self,
        *,
        pool: Knot | DatabaseConnectionPool,
        fact_table: Knot | str,
        fact_column: Knot | str,
        dimension_table: Knot | str,
        dimension_column: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            pool=pool,
            fact_table=fact_table,
            fact_column=fact_column,
            dimension_table=dimension_table,
            dimension_column=dimension_column,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        *,
        pool: Any,
        fact_table: Any,
        fact_column: Any,
        dimension_table: Any,
        dimension_column: Any,
        **_: Any,
    ) -> dict[str, Any]:
        """Count orphaned FK rows and compute orphan percentage.

        Returns:
            A dict with keys ``succeeded``, ``fact_table``,
            ``fact_column``, ``dimension_table``, ``dimension_column``,
            ``total_rows``, ``orphaned_rows``, ``orphaned_pct``,
            and ``has_orphans``.

        Raises:
            TypeError: When pool is not a DatabaseConnectionPool.
            ValueError: When any identifier is invalid.
        """
        if not isinstance(pool, DatabaseConnectionPool):
            raise TypeError(
                "ReferentialIntegrityCheck: pool must be a DatabaseConnectionPool"
            )
        IdentifierValidator.validate_column("fact_table", fact_table)
        IdentifierValidator.validate_column("fact_column", fact_column)
        IdentifierValidator.validate_column("dimension_table", dimension_table)
        IdentifierValidator.validate_column("dimension_column", dimension_column)
        total_rows_result = await pool.fetch_all(
            f"SELECT COUNT(*) FROM {fact_table}"
        )
        total_rows = total_rows_result[0][0]
        orphaned_rows_result = await pool.fetch_all(
            f"SELECT COUNT(*) FROM {fact_table} f "
            f"WHERE f.{fact_column} NOT IN "
            f"(SELECT {dimension_column} FROM {dimension_table})"
        )
        orphaned_rows = orphaned_rows_result[0][0]
        orphaned_pct = (
            (orphaned_rows / total_rows * 100.0) if total_rows > 0 else 0.0
        )
        return {
            "succeeded": True,
            "fact_table": fact_table,
            "fact_column": fact_column,
            "dimension_table": dimension_table,
            "dimension_column": dimension_column,
            "total_rows": total_rows,
            "orphaned_rows": orphaned_rows,
            "orphaned_pct": orphaned_pct,
            "has_orphans": orphaned_rows > 0,
        }
