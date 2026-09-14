"""``DuckdbTransaction`` — statements on the DuckDB connection a :class:`DuckdbPool` transaction holds.

Yielded by :meth:`DuckdbPool.transaction`, which opened a dedicated cursor
connection on the pool's database, called ``begin()`` on it, and commits or rolls
back when its scope ends. DuckDB is synchronous, so each statement runs in a
worker thread; none issues transaction control of its own.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from typing import Any

from pirn.connectors.database_transaction import DatabaseTransaction


class DuckdbTransaction(DatabaseTransaction):
    """Run statements inside the transaction a :class:`DuckdbPool` opened."""

    async def execute(self, query: str, parameters: Iterable[Any] | None = None) -> Any:
        self._check(query)
        return await asyncio.to_thread(self._connection.execute, query, list(parameters or ()))

    async def execute_many(self, query: str, parameter_seq: Iterable[Iterable[Any]]) -> Any:
        self._check(query)
        rows = [list(p) for p in parameter_seq]
        return await asyncio.to_thread(self._connection.executemany, query, rows)

    async def fetch_all(
        self, query: str, parameters: Iterable[Any] | None = None
    ) -> list[tuple[Any, ...]]:
        self._check(query)
        return await asyncio.to_thread(
            DuckdbTransaction._sync_fetch_all, self._connection, query, list(parameters or ())
        )

    @staticmethod
    def _sync_fetch_all(connection: Any, query: str, params: list[Any]) -> list[tuple[Any, ...]]:
        return [tuple(r) for r in connection.execute(query, params).fetchall()]
