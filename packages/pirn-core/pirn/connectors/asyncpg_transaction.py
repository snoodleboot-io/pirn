"""``AsyncpgTransaction`` — statements on the asyncpg connection a transaction scope holds.

Yielded by :meth:`PostgresPool.transaction`, :meth:`RedshiftPool.transaction` and
:meth:`TimescaleDBPool.transaction`. All three drive the same asyncpg surface, so
they share one handle: the owning pool has already started the connection's
``transaction()`` and commits or rolls back when its scope ends. The statements
here therefore issue no transaction control of their own.

asyncpg binds values variadically, so the interface's single ``parameters``
iterable is splatted here exactly as the pools do (PIR-833).

Algorithm:
    1. ``_check`` refuses a handle whose scope has ended and applies the owning
       pool's inline-interpolation guard to the query.
    2. The statement runs on the bound connection, inside the open transaction.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from pirn.connectors.database_transaction import DatabaseTransaction


class AsyncpgTransaction(DatabaseTransaction):
    """Run statements inside the transaction an asyncpg-backed pool opened."""

    async def execute(self, query: str, parameters: Iterable[Any] | None = None) -> str:
        """Run a parameterised statement; returns asyncpg's status string."""
        self._check(query)
        return await self._connection.execute(query, *tuple(parameters or ()))

    async def fetch_all(self, query: str, parameters: Iterable[Any] | None = None) -> list[Any]:
        """Run a parameterised read and return all rows."""
        self._check(query)
        rows = await self._connection.fetch(query, *tuple(parameters or ()))
        return list(rows)

    async def execute_many(self, query: str, parameter_seq: Iterable[Iterable[Any]]) -> None:
        """Run ``query`` once per bind-value iterable."""
        self._check(query)
        await self._connection.executemany(query, [tuple(p) for p in parameter_seq])
