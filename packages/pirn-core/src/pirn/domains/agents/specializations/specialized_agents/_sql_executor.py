"""``_SQLExecutor`` — internal helper Knot for :class:`SQLAgent`.

Validates a SQL statement through the connector pool's
``_reject_inline_interpolation`` guard and executes it. Internal API.

Algorithm:
    1. Receive the ``sql`` query string and ``pool`` connection pool.
    2. Raise :class:`ValueError` if ``sql`` is empty.
    3. Call ``pool._reject_inline_interpolation(sql)`` to guard against
       prompt-injected dynamic SQL and accidental ``str.format`` patterns.
    4. If the pool exposes ``fetch_all``, call it directly; otherwise
       acquire a connection, execute the query, fetch all rows, and
       release the connection.
    5. Return the rows as a plain list.

Math:
    No numeric computation.

References:
    - OWASP SQL injection prevention:
      https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html
"""

from __future__ import annotations

from typing import Any

from pirn.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class _SQLExecutor(Knot):
    """Validate the SQL through the pool guard and run it."""

    def __init__(
        self,
        *,
        sql: Knot | str,
        pool: Knot | DatabaseConnectionPool,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(sql=sql, pool=pool, _config=_config, **kwargs)

    async def process(self, sql: str, pool: DatabaseConnectionPool, **_: Any) -> list[Any]:
        """Validate the SQL against the inline-interpolation guard and execute it, returning the rows.

        Args:
            sql: The non-empty SQL query string to validate and execute.
            pool: The database connection pool used to execute the query.

        Returns:
            A list of row values returned by the database.

        Raises:
            ValueError: If sql is empty.
        """
        if not isinstance(sql, str) or not sql:
            raise ValueError("SQLAgent: generator returned empty SQL")
        # Defends against prompt-injected dynamic SQL and accidental
        # ``str.format`` interpolation in the generated query.
        pool._reject_inline_interpolation(sql)
        if hasattr(pool, "fetch_all"):
            rows = await pool.fetch_all(sql)  # type: ignore[attr-defined]
        else:
            connection = await pool.acquire()
            try:
                cursor = await connection.execute(sql)
                rows = await cursor.fetchall()
            finally:
                await pool.release(connection)
        return list(rows)
