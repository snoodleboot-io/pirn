"""``SqliteConnector`` — a zero-extra :class:`SqlConnector` over stdlib sqlite3.

Wraps an existing :class:`sqlite3.Connection` (e.g. an in-memory database) and
runs each query in a worker thread so the event loop is never blocked. Uses only
the standard library, so it is the default backend and needs no optional extra.

Because queries run on a thread-pool worker, the connection must be created with
``sqlite3.connect(..., check_same_thread=False)`` so SQLite's same-thread guard
does not reject the cross-thread use.
"""

from __future__ import annotations

import asyncio
import sqlite3
from collections.abc import Sequence
from typing import Any

from pirn_agents.tools.sql.sql_connector import SqlConnector


class SqliteConnector(SqlConnector):
    """Execute queries against a stdlib :class:`sqlite3.Connection`."""

    def __init__(self, *, connection: sqlite3.Connection) -> None:
        """Bind the connector to an open sqlite3 connection.

        Args:
            connection: The live :class:`sqlite3.Connection` to query.

        Raises:
            TypeError: If ``connection`` is not a :class:`sqlite3.Connection`.
        """
        if not isinstance(connection, sqlite3.Connection):
            raise TypeError(
                f"SqliteConnector: connection must be a sqlite3.Connection, "
                f"got {type(connection).__name__}"
            )
        self._connection: sqlite3.Connection = connection

    async def execute(
        self,
        query: str,
        parameters: Sequence[Any] | None = None,
    ) -> tuple[Sequence[str], Sequence[Sequence[Any]]]:
        """Run ``query`` in a worker thread and return ``(columns, rows)``."""
        return await asyncio.to_thread(self._execute_sync, query, parameters)

    def _execute_sync(
        self,
        query: str,
        parameters: Sequence[Any] | None,
    ) -> tuple[Sequence[str], Sequence[Sequence[Any]]]:
        """Synchronously execute ``query`` and materialise its result set."""
        cursor = self._connection.execute(query, tuple(parameters or ()))
        try:
            columns = [description[0] for description in cursor.description or ()]
            rows = [list(row) for row in cursor.fetchall()]
        finally:
            cursor.close()
        return columns, rows

    def _clear_credentials(self) -> None:
        """Drop the connection reference so it becomes garbage-collectable."""
        self._connection = None  # type: ignore[assignment]
