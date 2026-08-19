"""``ColumnAwareSqlitePool`` — core :class:`SqlitePool` with column-aware reads.

Reuses core's SQLite pooling lifecycle (lazy connect, single-connection reuse,
``close``, credential scrub, and the ``_reject_inline_interpolation`` guard) and
adds only the one thing core lacks for the agents ``sql_query`` tool: reads that
return column names alongside rows. Core's ``SqlitePool.fetch_all`` returns bare
tuples, so the column names come from the cursor description here.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.connectors.databases.sqlite_config import SqliteConfig
from pirn.connectors.databases.sqlite_pool import SqlitePool

from pirn_agents.connectors.column_aware_pool import ColumnAwarePool


class ColumnAwareSqlitePool(SqlitePool, ColumnAwarePool):
    """A core ``SqlitePool`` whose reads also carry column names."""

    def __init__(self, config: SqliteConfig, *, connection: Any | None = None) -> None:
        """Build the pool, optionally pre-seeding an injected connection.

        Args:
            config: Core :class:`SqliteConfig` (database path, pragmas, ...).
            connection: Optional pre-built aiosqlite-shaped connection. When
                supplied it seeds core's single-connection slot, so ``acquire``
                returns it without opening the real backend — the seam mirrored
                tests use to run offline without the ``[sql]`` extra.
        """
        super().__init__(config)
        if connection is not None:
            self._connection = connection

    async def fetch_columns(
        self, query: str, parameters: Sequence[Any] | None = None
    ) -> tuple[list[str], list[list[Any]]]:
        """Run a read and return ``(column names, rows)``.

        Core's ``_reject_inline_interpolation`` guard is deliberately not applied:
        its ``%[sd]`` / ``{...}`` pattern false-positives on legitimate literals a
        read query commonly contains (``LIKE '%term%'``, JSON ``{...}``), and this
        connector's defences are read-only mode plus bound parameters — SQLite uses
        ``?`` / ``:name`` markers, never ``%s``, so a literal ``%`` is always data.

        **Transaction ownership.** This method commits — or rolls back — exactly the
        transaction *its own statement* opened, and never touches one it found
        already open. ``sqlite3`` starts an implicit transaction for DML only, so
        comparing ``in_transaction`` before and after the statement identifies the
        owner precisely:

        * a write that succeeds is committed, so it is durable once this returns —
          without that, a write reaching this method (the only path
          ``SqlServiceConnector(read_only=False)`` has) was discarded when the
          connection closed, silently and with no error (PIR-801);
        * a statement that raises is rolled back. ``UPDATE ... OR FAIL`` aborts
          mid-statement while *keeping* the rows it already changed and leaves the
          transaction open, so without the rollback that partial write survived to
          be committed by whatever ran next — including a pure read;
        * a read, and DDL, open no transaction and so neither commit nor roll back.
          A read therefore issues no ``COMMIT``, which matters beyond tidiness:
          under ``journal_mode=DELETE`` a ``COMMIT`` must take the exclusive lock,
          so a concurrent reader would make a query that only read rows fail with
          ``database is locked``.

        A caller driving this pool directly can therefore hold a multi-statement
        transaction across these calls and remains the only one who may end it.
        """
        connection = await self.acquire()
        in_transaction_on_entry = bool(connection.in_transaction)
        try:
            cursor = await connection.execute(query, tuple(parameters or ()))
            try:
                fetched = await cursor.fetchall()
                columns = [description[0] for description in cursor.description or ()]
            finally:
                await cursor.close()
        except BaseException:
            if self._opened_transaction(connection, in_transaction_on_entry):
                await connection.rollback()
            raise
        if self._opened_transaction(connection, in_transaction_on_entry):
            await connection.commit()
        return columns, [list(row) for row in fetched]

    @staticmethod
    def _opened_transaction(connection: Any, in_transaction_on_entry: bool) -> bool:
        """Whether the statement just run is what opened the now-open transaction.

        Args:
            connection: The aiosqlite-shaped connection the statement ran on.
            in_transaction_on_entry: ``connection.in_transaction`` sampled before
                the statement ran.

        Returns:
            ``True`` only when a transaction is open now and none was open before,
            which makes this call its owner — and so the one responsible for
            ending it.
        """
        return bool(connection.in_transaction) and not in_transaction_on_entry
