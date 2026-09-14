"""``SqliteTransaction`` — statements on the aiosqlite connection a :class:`SqlitePool` transaction holds.

Yielded by :meth:`SqlitePool.transaction`, which has already issued ``BEGIN`` on
the pool's single connection and commits or rolls back when its scope ends. The
statements here therefore issue no transaction control: they run on the open
transaction and leave ending it to the scope.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from pirn.connectors.database_transaction import DatabaseTransaction


class SqliteTransaction(DatabaseTransaction):
    """Run statements inside the transaction a :class:`SqlitePool` opened."""

    async def execute(self, query: str, parameters: Iterable[Any] | None = None) -> Any:
        self._check(query)
        return await self._connection.execute(query, tuple(parameters or ()))

    async def execute_many(self, query: str, parameter_seq: Iterable[Iterable[Any]]) -> Any:
        self._check(query)
        return await self._connection.executemany(query, [tuple(p) for p in parameter_seq])

    async def fetch_all(
        self, query: str, parameters: Iterable[Any] | None = None
    ) -> list[tuple[Any, ...]]:
        self._check(query)
        cursor = await self._connection.execute(query, tuple(parameters or ()))
        try:
            rows = await cursor.fetchall()
        finally:
            await cursor.close()
        return [tuple(r) for r in rows]
