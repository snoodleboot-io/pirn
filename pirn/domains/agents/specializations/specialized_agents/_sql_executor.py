"""``_SQLExecutor`` — internal helper Knot for :class:`SQLAgent`.

Validates a SQL statement through the connector pool's
``_reject_inline_interpolation`` guard and executes it. Internal API.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)


class _SQLExecutor(Knot):
    """Validate the SQL through the pool guard and run it."""

    def __init__(
        self,
        *,
        sql: Knot,
        pool: DatabaseConnectionPool,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        self._pool = pool
        super().__init__(sql=sql, _config=_config, **kwargs)

    async def process(self, sql: str, **_: Any) -> list[Any]:
        """Validate the SQL against the inline-interpolation guard and execute it, returning the rows.

        Args:
            sql: The non-empty SQL query string to validate and execute.

        Returns:
            A list of row values returned by the database.

        Raises:
            ValueError: If sql is empty.
        """
        if not isinstance(sql, str) or not sql:
            raise ValueError(
                "SQLAgent: generator returned empty SQL"
            )
        # Defends against prompt-injected dynamic SQL and accidental
        # ``str.format`` interpolation in the generated query.
        self._pool._reject_inline_interpolation(sql)
        if hasattr(self._pool, "fetch_all"):
            rows = await self._pool.fetch_all(sql)
        else:
            connection = await self._pool.acquire()
            try:
                cursor = await connection.execute(sql)
                rows = await cursor.fetchall()
            finally:
                await self._pool.release(connection)
        return list(rows)
