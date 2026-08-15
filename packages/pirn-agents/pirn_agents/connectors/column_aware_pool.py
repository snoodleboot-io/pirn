"""``ColumnAwarePool`` — a core connection pool that also returns column names.

Core's :class:`~pirn.connectors.database_connection_pool.DatabaseConnectionPool`
returns rows only (``fetch_all -> list[Any]``); its ``SqlitePool`` discards column
names entirely (bare tuples). The agents ``sql_query`` tool must return column
names to the LLM, so this interface adds one column-aware read on top of the core
pool surface, which agents' concrete pools implement by reusing core's
acquire/close/config/credential-scrubbing lifecycle.

It is the seam the agents SQL connector depends on (ISP): the connector needs
``fetch_columns`` plus the inherited ``close``, nothing else.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.connectors.database_connection_pool import DatabaseConnectionPool


class ColumnAwarePool(DatabaseConnectionPool):
    """A ``DatabaseConnectionPool`` whose reads also carry column names."""

    async def fetch_columns(
        self, query: str, parameters: Sequence[Any] | None = None
    ) -> tuple[list[str], list[list[Any]]]:
        """Run ``query`` with bound ``parameters`` and return ``(columns, rows)``.

        The concrete pool applies core's ``_reject_inline_interpolation`` guard
        before executing, so the same injection defence as core's ``fetch_all``
        still holds. Rows are returned uncapped; the caller applies any row cap.

        **Durability contract.** An implementation owns exactly the transaction its
        own statement opens, and no other:

        * a statement that succeeds leaves no uncommitted work behind — when this
          returns, any effect of ``query`` is durable;
        * a statement that raises leaves nothing behind at all, including a partial
          write it made before failing;
        * a transaction the caller already had open is left untouched — neither
          committed nor rolled back — so a caller may hold one across these calls.

        This is not automatic. The SQLite implementation tracks ownership across
        ``in_transaction`` and commits or rolls back explicitly, while asyncpg
        satisfies the whole contract for free by autocommitting outside an explicit
        transaction. Before PIR-801 the SQLite pool never committed, so the same
        call was durable on Postgres and silently discarded on SQLite; committing
        unconditionally then swung it the other way, adopting work the call had not
        done.

        Raises:
            NotImplementedError: Always, in the interface.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement fetch_columns()")
