"""``ThreadedCursorTransaction`` — statements on the sync DB-API client a transaction holds.

Yielded by :meth:`OraclePool.transaction` and :meth:`SnowflakePool.transaction`.
Both drive a *synchronous* DB-API client (``oracledb``, ``snowflake.connector``)
and keep the event loop free by running every call in a worker thread, so they
share one handle. The owning pool has already begun the transaction on the client
and commits or rolls back when its scope ends; the statements here issue no
transaction control of their own.

Algorithm:
    1. ``_check`` refuses a handle whose scope has ended and applies the owning
       pool's inline-interpolation guard to the query.
    2. The whole cursor cycle — open, execute, fetch, close — runs in one
       ``asyncio.to_thread`` call, so the cursor never crosses a thread boundary
       and the connection is touched by one thread at a time.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from typing import Any

from pirn.connectors.database_transaction import DatabaseTransaction


class ThreadedCursorTransaction(DatabaseTransaction):
    """Run statements inside the transaction a thread-offloaded DB-API pool opened."""

    async def execute(self, query: str, parameters: Iterable[Any] | None = None) -> Any:
        """Run a parameterised statement; returns the cursor's row count."""
        self._check(query)
        return await asyncio.to_thread(
            self._sync_execute, self._connection, query, list(parameters or ())
        )

    async def fetch_all(
        self, query: str, parameters: Iterable[Any] | None = None
    ) -> list[tuple[Any, ...]]:
        """Run a parameterised read and return all rows as tuples."""
        self._check(query)
        return await asyncio.to_thread(
            self._sync_fetch_all, self._connection, query, list(parameters or ())
        )

    async def execute_many(self, query: str, parameter_seq: Iterable[Iterable[Any]]) -> Any:
        """Run ``query`` once per bind-value iterable; returns the cursor's row count."""
        self._check(query)
        return await asyncio.to_thread(
            self._sync_execute_many, self._connection, query, [list(p) for p in parameter_seq]
        )

    @staticmethod
    def _sync_execute(connection: Any, query: str, params: list[Any]) -> Any:
        cursor = connection.cursor()
        try:
            cursor.execute(query, params)
            return getattr(cursor, "rowcount", None)
        finally:
            cursor.close()

    @staticmethod
    def _sync_fetch_all(connection: Any, query: str, params: list[Any]) -> list[tuple[Any, ...]]:
        cursor = connection.cursor()
        try:
            cursor.execute(query, params)
            return [tuple(r) for r in cursor.fetchall()]
        finally:
            cursor.close()

    @staticmethod
    def _sync_execute_many(connection: Any, query: str, rows: list[list[Any]]) -> Any:
        cursor = connection.cursor()
        try:
            cursor.executemany(query, rows)
            return getattr(cursor, "rowcount", None)
        finally:
            cursor.close()
