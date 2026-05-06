"""``TruncateTableKnot`` — delete every row from a target table.

Used by :class:`FullRefreshExtract` as the gate step before reloading.
Identifier guards (alphanumeric + underscores) prevent injection; pool
and table arrive as resolved values in ``process()``, not stored state.

Algorithm:
    1. Receive ``pool`` and ``table`` in ``process()``.
    2. Validate that ``pool`` is a ``DatabaseConnectionPool`` and ``table``
       is a non-empty alphanumeric string (underscores allowed).
    3. Issue ``DELETE FROM <table>`` via the pool.
    4. Return the table name so downstream knots can use it as a signal.

References:
    [1] pirn — DatabaseConnectionPool interface:
        pirn/domains/connectors/database_connection_pool.py
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool


class TruncateTableKnot(Knot):
    """Run ``DELETE FROM <table>`` and return the table name."""

    def __init__(
        self,
        *,
        pool: Knot | DatabaseConnectionPool,
        table: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(pool=pool, table=table, _config=_config, **kwargs)

    async def process(self, *, pool: Any, table: Any, **_: Any) -> str:
        """Validate inputs, delete all rows from the table, and return the table name.

        Args:
            pool: The database connection pool used to execute the DELETE.
            table: The name of the table to truncate.

        Returns:
            The name of the table that was truncated.

        Raises:
            TypeError: If ``pool`` is not a ``DatabaseConnectionPool``.
            ValueError: If ``table`` is empty or contains non-alphanumeric characters.
        """
        if not isinstance(pool, DatabaseConnectionPool):
            raise TypeError("TruncateTableKnot: pool must be a DatabaseConnectionPool")
        if not isinstance(table, str) or not table:
            raise ValueError("TruncateTableKnot: table must be a non-empty string")
        if not table.replace("_", "").isalnum():
            raise ValueError(
                f"TruncateTableKnot: table {table!r} must be alphanumeric (plus underscores)"
            )
        await pool.execute(f"DELETE FROM {table}")
        return table
