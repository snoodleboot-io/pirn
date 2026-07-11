"""``SqlQueryTool`` — run a read-only, row-capped SQL query via a connector."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn_agents.tools.base_tool import BaseTool
from pirn_agents.tools.sql._read_only_guard import assert_read_only
from pirn_agents.tools.sql.sql_connector import SqlConnector


class SqlQueryTool(BaseTool):
    """Execute a SQL query, enforcing read-only mode and a max-row cap."""

    def __init__(
        self,
        *,
        connector: SqlConnector,
        read_only: bool = True,
        max_rows: int = 1000,
    ) -> None:
        """Bind the tool to a connector and its safety policy.

        Args:
            connector: The injected :class:`SqlConnector` executing the query.
            read_only: When ``True`` (default), reject any non-SELECT statement.
            max_rows: Maximum number of rows returned; extra rows are dropped and
                the result is flagged truncated.

        Raises:
            TypeError: If ``connector`` is not a :class:`SqlConnector`.
            ValueError: If ``max_rows`` is not positive.
        """
        if not isinstance(connector, SqlConnector):
            raise TypeError(
                f"sql_query: connector must be a SqlConnector, got {type(connector).__name__}"
            )
        if max_rows <= 0:
            raise ValueError(f"sql_query: max_rows must be positive, got {max_rows}")
        self._connector = connector
        self._read_only = read_only
        self._max_rows = max_rows

    @property
    def name(self) -> str:
        """Return the stable tool identifier ``"sql_query"``."""
        return "sql_query"

    @property
    def description(self) -> str:
        """Return the human-readable description shown to the planner."""
        mode = "read-only SELECT/WITH" if self._read_only else "arbitrary"
        return f"Run a {mode} SQL query and return columns and rows (capped)."

    @property
    def parameters_schema(self) -> Mapping[str, Any]:
        """Return the JSON Schema for the ``query`` and optional ``parameters``."""
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The SQL query to execute."},
                "parameters": {
                    "type": "array",
                    "description": "Optional positional bind parameters for the query.",
                },
            },
            "required": ["query"],
        }

    async def invoke(self, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        """Execute the query (read-only guarded) and return capped results.

        Returns:
            ``{"columns", "rows", "row_count", "truncated"}``.

        Raises:
            TypeError: If ``arguments`` is not a mapping.
            ValueError: If ``query`` is missing, or read-only mode rejects it.
        """
        self._require_mapping(self.name, arguments)
        query = self._string_argument(self.name, arguments, "query")
        if self._read_only:
            assert_read_only(query)
        parameters = self._coerce_parameters(arguments.get("parameters"))
        columns, rows = await self._connector.execute(query, parameters)
        row_list = list(rows)
        truncated = len(row_list) > self._max_rows
        capped = [list(row) for row in row_list[: self._max_rows]]
        return {
            "columns": list(columns),
            "rows": capped,
            "row_count": len(capped),
            "truncated": truncated,
        }

    @staticmethod
    def _coerce_parameters(raw: Any) -> Sequence[Any] | None:
        """Validate optional bind parameters, returning ``None`` when absent."""
        if raw is None:
            return None
        if not isinstance(raw, (list, tuple)):
            raise ValueError(
                f"sql_query: 'parameters' must be a list/tuple, got {type(raw).__name__}"
            )
        return list(raw)
