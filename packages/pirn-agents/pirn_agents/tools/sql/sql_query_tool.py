"""``SqlQueryTool`` — run a read-only, row-capped SQL query via a bound connector."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Annotated, Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pydantic import Field

from pirn_agents.tools.sql._read_only_sql_guard import ReadOnlySqlGuard
from pirn_agents.tools.sql.sql_connector import SqlConnector
from pirn_agents.tools.tool import Tool


class SqlQueryTool(Tool):
    """Run a SQL query and return columns and rows (capped); read-only SELECT/WITH by default."""

    tool_name: ClassVar[str] = "sql_query"

    def __init__(
        self,
        *,
        query: Knot | str,
        connector: Knot | SqlConnector,
        parameters: Knot | Sequence[Any] | None = None,
        read_only: Knot | bool = True,
        max_rows: Knot | int = 1000,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            query=query,
            connector=connector,
            parameters=parameters,
            read_only=read_only,
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
        read_only: bool = True,
        max_rows: int = 1000,
        **_: Any,
    ) -> Mapping[str, Any]:
        """Execute the query (read-only guarded) and return capped results.

        Args:
            query: The SQL query to execute.
            connector: The :class:`SqlConnector` executing the query; bound
                once with ``SqlQueryTool.bind(connector=...)``.
            parameters: Optional positional bind parameters.
            read_only: When ``True`` (default), reject any non-SELECT statement.
                Bound policy: a pipeline author decides once whether the tool
                may mutate; the declaration hides it from the model.
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
        if read_only:
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
