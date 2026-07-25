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

        Raises:
            NotImplementedError: Always, in the interface.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement fetch_columns()")
