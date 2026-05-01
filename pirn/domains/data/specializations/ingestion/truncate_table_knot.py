"""``TruncateTableKnot`` — internal helper used by
:class:`FullRefreshExtract` to delete every row from a target table.

Pool is held as instance state. Table name is validated as alphanumeric
(plus underscores) at construction time; pirn's connection-pool
identifiers come from configuration, not user input, but this guard
catches typos and refuses anything that looks abusive.
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
        pool: DatabaseConnectionPool,
        table: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(pool, DatabaseConnectionPool):
            raise TypeError(
                "TruncateTableKnot: pool must be a DatabaseConnectionPool"
            )
        if not isinstance(table, str) or not table:
            raise ValueError("TruncateTableKnot: table must be a non-empty string")
        if not table.replace("_", "").isalnum():
            raise ValueError(
                f"TruncateTableKnot: table {table!r} must be alphanumeric "
                "(plus underscores)"
            )
        self._pool = pool
        self._table = table
        super().__init__(_config=_config, **kwargs)

    @property
    def table(self) -> str:
        return self._table

    async def process(self, **_: Any) -> str:
        await self._pool.execute(f"DELETE FROM {self._table}")
        return self._table
