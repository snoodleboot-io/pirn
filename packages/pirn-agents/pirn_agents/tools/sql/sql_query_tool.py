"""``SqlQueryTool`` — run a read-only, row-capped SQL query via a bound connector.

Whether the statement may mutate is not an input: it is the class
(:class:`~pirn_agents.tools.sql.read_write_sql_query_tool.ReadWriteSqlQueryTool`
is the one that may write).  ``read_only`` used to be a ``Knot | bool`` input
defaulting to ``True``, which made the guard part of the tool's model-facing
declaration: any call not built through ``bind`` could carry
``read_only: false`` and the model's own statement would then run unguarded.
A policy that must not be driven by a knot's output is a ``ClassVar`` on
distinct classes (PIR-817, ``docs/contributing/knot-design-rules.md`` Rule 4).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Annotated, Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pydantic import Field

from pirn_agents.tools.sql.read_only_sql_guard import ReadOnlySqlGuard
from pirn_agents.tools.sql.sql_connector import SqlConnector
from pirn_agents.tools.tool import Tool


class SqlQueryTool(Tool):
    """Run a SQL query and return columns and rows (capped); read-only SELECT/WITH by default."""

    tool_name: ClassVar[str] = "sql_query"

    #: The write policy is the class, never an input (PIR-817): this tool is
    #: read-only and
    #: :class:`~pirn_agents.tools.sql.read_write_sql_query_tool.ReadWriteSqlQueryTool`
    #: is the one subclass that may run a mutating statement.  A knot input is
    #: a graph edge some other knot's output — here, output derived from model
    #: text — could drive, and it is part of the declaration the model reads.
    _read_only: ClassVar[bool] = True

    def __init__(
        self,
        *,
        query: Knot | str,
        connector: Knot | SqlConnector,
        parameters: Knot | Sequence[Any] | None = None,
        max_rows: Knot | int = 1000,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            query=query,
            connector=connector,
            parameters=parameters,
            max_rows=max_rows,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        query: Annotated[str, Field(description="The SQL query to execute.")],
        connector: SqlConnector,
        parameters: Annotated[
            list[Any] | None,
            Field(description="Optional positional bind parameters for the query."),
        ] = None,
        max_rows: int = 1000,
        **_: Any,
    ) -> Mapping[str, Any]:
        """Execute the query (read-only guarded) and return capped results.

        Args:
            query: The SQL query to execute.
            connector: The :class:`SqlConnector` executing the query; bound
                once with ``SqlQueryTool.bind(connector=...)``.
            parameters: Optional positional bind parameters.
            max_rows: Maximum number of rows returned; extra rows are dropped
                and the result is flagged truncated.

        Returns:
            ``{"columns", "rows", "row_count", "truncated"}``.

        Raises:
            ValueError: If ``query`` is empty, ``max_rows`` is not positive, or
                read-only mode rejects the statement.
        """
        if max_rows <= 0:
            raise ValueError(f"sql_query: max_rows must be positive, got {max_rows}")
        if not query:
            raise ValueError("sql_query: 'query' must be a non-empty string")
        if self._read_only:
            ReadOnlySqlGuard().assert_read_only(query)
        columns, rows = await connector.execute(query, list(parameters) if parameters else None)
        row_list = list(rows)
        truncated = len(row_list) > max_rows
        capped = [list(row) for row in row_list[:max_rows]]
        return {
            "columns": list(columns),
            "rows": capped,
            "row_count": len(capped),
            "truncated": truncated,
        }
