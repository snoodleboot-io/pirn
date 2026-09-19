"""``ReadWriteSqlQueryTool`` — the write-enabled sibling of :class:`SqlQueryTool`.

Identical to :class:`~pirn_agents.tools.sql.sql_query_tool.SqlQueryTool` except
that it skips the read-only guard, so the statement it is handed may mutate.
Writing is chosen by constructing this class rather than by a knot input, so no
upstream knot's output — on an agent pipeline, output derived from model text —
and no argument the model puts in its call can ever flip it (PIR-817).

The row cap still applies, and the tool is addressed by a different name
(``sql_write``) so a toolset offering both is unambiguous to the model.

References:
    pirn-native — no external references.
"""

from __future__ import annotations

from typing import ClassVar

from pirn_agents.tools.sql.sql_query_tool import SqlQueryTool


class ReadWriteSqlQueryTool(SqlQueryTool):
    """Run a SQL statement that may mutate, and return columns and rows (capped)."""

    tool_name: ClassVar[str] = "sql_write"

    _read_only: ClassVar[bool] = False
