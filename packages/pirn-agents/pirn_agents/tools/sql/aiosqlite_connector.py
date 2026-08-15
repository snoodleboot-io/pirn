"""``AiosqliteConnector`` — async :class:`SqlConnector` backed by ``aiosqlite``.

Demonstrates the "SQL driver lazily imported behind an extra" pattern: the
``aiosqlite`` backend is imported only inside :meth:`execute` via
:func:`~pirn_agents._internal._require._require`, so importing this module stays
backend-free. Install with ``pip install "pirn-agents[sql]"``.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn_agents._internal._require import _require
from pirn_agents.tools.sql.sql_connector import SqlConnector


class AiosqliteConnector(SqlConnector):
    """Execute queries against a SQLite database file using ``aiosqlite``."""

    def __init__(self, *, database: str) -> None:
        """Bind the connector to a SQLite database path/URI.

        Args:
            database: Path (or URI) of the SQLite database to open per query.
        """
        self._database = database

    async def execute(
        self,
        query: str,
        parameters: Sequence[Any] | None = None,
    ) -> tuple[Sequence[str], Sequence[Sequence[Any]]]:
        """Open the database, run ``query``, and return ``(columns, rows)``.

        **Transaction ownership.** This method commits — or rolls back — exactly
        the transaction *its own statement* opened, the same guarantee
        :meth:`~pirn_agents.connectors.column_aware_sqlite_pool.ColumnAwareSqlitePool.fetch_columns`
        makes (PIR-801). The connection is opened here and never shared, so
        nothing else can have started a transaction on it and
        ``in_transaction`` *is* ownership; a pool that hands out a shared
        connection must additionally sample the flag on entry to tell its own
        transaction from a caller's.

        ``sqlite3`` starts an implicit transaction for DML only, so the flag
        separates the three outcomes precisely:

        * a write that succeeds is committed, so it is durable once this returns
          — without that, every write through this connector was discarded when
          the per-query connection closed, silently and with no error. Because
          ``sqlite3`` autocommits DDL, a ``CREATE TABLE`` survived while the
          ``INSERT`` after it did not, leaving a database with a full schema and
          no rows (PIR-807);
        * a statement that raises is rolled back rather than left open;
        * a read, and DDL, open no transaction and so neither commit nor roll
          back. Issuing no ``COMMIT`` for a read matters beyond tidiness: under
          ``journal_mode=DELETE`` a ``COMMIT`` must take the exclusive lock, so a
          concurrent reader would make a query that only read rows fail with
          ``database is locked``.

        Raises:
            ImportError: If the ``aiosqlite`` backend is not installed.
        """
        aiosqlite = _require("sql", "aiosqlite")
        async with aiosqlite.connect(self._database) as db:
            try:
                cursor = await db.execute(query, tuple(parameters or ()))
                try:
                    fetched = await cursor.fetchall()
                    columns = [description[0] for description in cursor.description or ()]
                finally:
                    await cursor.close()
            except BaseException:
                if db.in_transaction:
                    await db.rollback()
                raise
            if db.in_transaction:
                await db.commit()
        rows = [list(row) for row in fetched]
        return columns, rows
