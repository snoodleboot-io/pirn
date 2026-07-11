"""``AiosqliteConnector`` — async :class:`SqlConnector` backed by ``aiosqlite``.

Demonstrates the "SQL driver lazily imported behind an extra" pattern: the
``aiosqlite`` backend is imported only inside :meth:`execute` via
:func:`~pirn_agents._require._require`, so importing this module stays
backend-free. Install with ``pip install "pirn-agents[sql]"``.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn_agents._require import _require
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

        Raises:
            ImportError: If the ``aiosqlite`` backend is not installed.
        """
        aiosqlite = _require("sql", "aiosqlite")
        async with aiosqlite.connect(self._database) as db:
            cursor = await db.execute(query, tuple(parameters or ()))
            try:
                fetched = await cursor.fetchall()
                columns = [description[0] for description in cursor.description or ()]
            finally:
                await cursor.close()
        rows = [list(row) for row in fetched]
        return columns, rows
