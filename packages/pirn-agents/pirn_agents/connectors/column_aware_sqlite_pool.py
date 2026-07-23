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
        """
        connection = await self.acquire()
        cursor = await connection.execute(query, tuple(parameters or ()))
        try:
            fetched = await cursor.fetchall()
            columns = [description[0] for description in cursor.description or ()]
        finally:
            await cursor.close()
        return columns, [list(row) for row in fetched]
