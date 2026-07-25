"""``SqlConnector`` — provider-neutral interface for a SQL query backend.

:class:`~pirn_agents.tools.sql.sql_query_tool.SqlQueryTool` delegates to an
injected :class:`SqlConnector`, so no database driver is hard-wired. Concrete
connectors (stdlib sqlite, an async driver behind an extra, a test double)
implement :meth:`execute` and return ``(columns, rows)``.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


class SqlConnector(PirnOpaqueValue):
    """Interface every SQL query backend must satisfy."""

    async def execute(
        self,
        query: str,
        parameters: Sequence[Any] | None = None,
    ) -> tuple[Sequence[str], Sequence[Sequence[Any]]]:
        """Run ``query`` with optional bound ``parameters`` and return results.

        Returns:
            A ``(columns, rows)`` pair: ``columns`` is the ordered column-name
            sequence and ``rows`` is a sequence of row value sequences.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement execute()")
