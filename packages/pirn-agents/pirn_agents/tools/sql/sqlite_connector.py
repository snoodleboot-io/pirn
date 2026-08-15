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
        """Synchronously execute ``query`` and materialise its result set.

        **Transaction ownership.** This commits — or rolls back — exactly the
        transaction *its own statement* opened, and never touches one the caller
        already had open: the same guarantee
        :meth:`~pirn_agents.connectors.column_aware_sqlite_pool.ColumnAwareSqlitePool.fetch_columns`
        makes (PIR-801). The connection here is *caller-owned* and long-lived, so
        sampling ``in_transaction`` before and after the statement is what makes
        committing safe — it is the discriminator that identifies the owner.

        ``sqlite3`` starts an implicit transaction for DML only, which separates
        the outcomes precisely:

        * a write that succeeds is committed, so it is durable once this returns.
          Previously nothing here committed, so under the default
          ``isolation_level`` a write was lost whenever the caller closed the
          connection without committing, and was invisible to any other
          connection until they did (PIR-807);
        * a statement that raises is rolled back. ``UPDATE ... OR FAIL`` aborts
          mid-statement while *keeping* the rows it already changed and leaves
          the transaction open, so without the rollback that partial write
          survives on this long-lived connection to be committed by whatever runs
          next — including a pure read;
        * a read, and DDL, open no transaction and so neither commit nor roll
          back, leaving a caller who opened their own transaction — or who set
          ``isolation_level=None`` for autocommit — in sole control of it.

        Each statement therefore stands alone; a caller who needs several in one
        transaction must open it on the connection themselves, and remains the
        only one who may end it.
        """
        connection = self._connection
        in_transaction_on_entry = bool(connection.in_transaction)
        try:
            cursor = connection.execute(query, tuple(parameters or ()))
            try:
                columns = [description[0] for description in cursor.description or ()]
                rows = [list(row) for row in cursor.fetchall()]
            finally:
                cursor.close()
        except BaseException:
            if self._opened_transaction(connection, in_transaction_on_entry):
                connection.rollback()
            raise
        if self._opened_transaction(connection, in_transaction_on_entry):
            connection.commit()
        return columns, rows

    @staticmethod
    def _opened_transaction(connection: sqlite3.Connection, in_transaction_on_entry: bool) -> bool:
        """Whether the statement just run is what opened the now-open transaction.

        Args:
            connection: The connection the statement ran on.
            in_transaction_on_entry: ``connection.in_transaction`` sampled before
                the statement ran.

        Returns:
            ``True`` only when a transaction is open now and none was open
            before, which makes this call its owner — and so the one responsible
            for ending it.
        """
        return bool(connection.in_transaction) and not in_transaction_on_entry

    def _clear_credentials(self) -> None:
        """Drop the connection reference so it becomes garbage-collectable."""
        self._connection = None  # type: ignore[assignment]
