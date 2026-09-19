"""``DbapiCursorTransaction`` — statements on the async DB-API connection a transaction holds.

Yielded by :meth:`MySQLPool.transaction` and :meth:`MssqlPool.transaction`. Both
drive an async DB-API connection (aiomysql, aioodbc) whose statements go through
``await connection.cursor()``, so they share one handle: the owning pool has
already begun the transaction on the checked-out connection and commits or rolls
back when its scope ends. The statements here therefore issue no transaction
control of their own and do not release the connection.

Algorithm:
    1. ``_check`` refuses a handle whose scope has ended and applies the owning
       pool's inline-interpolation guard to the query.
    2. A cursor is opened on the bound connection, the statement runs inside the
       open transaction, and the cursor is closed whether or not it raised.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from pirn.connectors.database_transaction import DatabaseTransaction


class DbapiCursorTransaction(DatabaseTransaction):
    """Run statements inside the transaction an async DB-API pool opened."""

    async def execute(self, query: str, parameters: Iterable[Any] | None = None) -> Any:
        """Run a parameterised statement; returns the cursor's row count."""
        self._check(query)
        cursor = await self._connection.cursor()
        try:
            await cursor.execute(query, list(parameters or ()))
            return getattr(cursor, "rowcount", None)
        finally:
            await cursor.close()

    async def fetch_all(
        self, query: str, parameters: Iterable[Any] | None = None
    ) -> list[tuple[Any, ...]]:
        """Run a parameterised read and return all rows as tuples."""
        self._check(query)
        cursor = await self._connection.cursor()
        try:
            await cursor.execute(query, list(parameters or ()))
            rows = await cursor.fetchall()
        finally:
            await cursor.close()
        return [tuple(r) for r in rows]

    async def execute_many(self, query: str, parameter_seq: Iterable[Iterable[Any]]) -> Any:
        """Run ``query`` once per bind-value iterable; returns the cursor's row count."""
        self._check(query)
        cursor = await self._connection.cursor()
        try:
            await cursor.executemany(query, [list(p) for p in parameter_seq])
            return getattr(cursor, "rowcount", None)
        finally:
            await cursor.close()
