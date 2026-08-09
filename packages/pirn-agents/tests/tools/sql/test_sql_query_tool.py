"""Mirrored tests for the sql_query tool with a stub connector (PIR-163).

Covers read-only enforcement (rejecting DML/DDL and stacked statements),
row-cap truncation, the typed F1 result shape, parameter passthrough, the stdlib
:class:`SqliteConnector`, the friendly missing-``aiosqlite`` install error
(forced via ``patch.dict(sys.modules, {"aiosqlite": None})``), and the
:class:`SqlServiceConnector` interface conformance the tool type-checks (PIR-786).
"""

from __future__ import annotations

import sqlite3
import sys
from collections.abc import Sequence
from typing import Any
from unittest import mock

import pytest

from pirn_agents.connectors.column_aware_pool import ColumnAwarePool
from pirn_agents.connectors.sql_service_connector import SqlServiceConnector
from pirn_agents.tools.sql.aiosqlite_connector import AiosqliteConnector
from pirn_agents.tools.sql.sql_connector import SqlConnector
from pirn_agents.tools.sql.sql_query_tool import SqlQueryTool
from pirn_agents.tools.sql.sqlite_connector import SqliteConnector
from pirn_agents.tools.tool_call import ToolCall
from pirn_agents.tools.tool_status import ToolStatus


class _StubSqlConnector(SqlConnector):
    def __init__(self, columns: Sequence[str], rows: Sequence[Sequence[Any]]) -> None:
        self._columns = list(columns)
        self._rows = [list(r) for r in rows]
        self.calls: list[tuple[str, Sequence[Any] | None]] = []

    async def execute(
        self,
        query: str,
        parameters: Sequence[Any] | None = None,
    ) -> tuple[Sequence[str], Sequence[Sequence[Any]]]:
        self.calls.append((query, parameters))
        return self._columns, self._rows


class TestReadOnlyEnforcement:
    @pytest.mark.parametrize(
        "query",
        [
            "INSERT INTO t VALUES (1)",
            "UPDATE t SET x = 1",
            "DELETE FROM t",
            "DROP TABLE t",
            "ALTER TABLE t ADD COLUMN y int",
            "CREATE TABLE t (x int)",
            "SELECT 1; DROP TABLE t",
            "WITH x AS (SELECT 1) DELETE FROM t",
            "PRAGMA table_info(t)",
        ],
    )
    async def test_rejects_writes(self, query: str) -> None:
        tool = SqlQueryTool(connector=_StubSqlConnector(["a"], [[1]]))
        with pytest.raises(ValueError):
            await tool.invoke({"query": query})

    async def test_allows_select_and_with(self) -> None:
        connector = _StubSqlConnector(["n"], [[1]])
        tool = SqlQueryTool(connector=connector)
        await tool.invoke({"query": "SELECT n FROM t"})
        await tool.invoke({"query": "WITH c AS (SELECT 1) SELECT * FROM c"})
        assert len(connector.calls) == 2

    async def test_keyword_in_string_literal_is_allowed(self) -> None:
        connector = _StubSqlConnector(["label"], [["please delete me"]])
        tool = SqlQueryTool(connector=connector)
        result = await tool.invoke({"query": "SELECT label FROM t WHERE label = 'delete from x'"})
        assert result["row_count"] == 1

    async def test_write_allowed_when_read_only_disabled(self) -> None:
        connector = _StubSqlConnector([], [])
        tool = SqlQueryTool(connector=connector, read_only=False)
        await tool.invoke({"query": "UPDATE t SET x = 1"})
        assert connector.calls[-1][0] == "UPDATE t SET x = 1"


class TestRowCapAndShape:
    async def test_caps_rows_and_flags_truncation(self) -> None:
        rows = [[i] for i in range(100)]
        tool = SqlQueryTool(connector=_StubSqlConnector(["n"], rows), max_rows=10)
        result = await tool.invoke({"query": "SELECT n FROM t"})
        assert result["row_count"] == 10
        assert result["truncated"] is True
        assert result["columns"] == ["n"]
        assert result["rows"][0] == [0]

    async def test_no_truncation_under_cap(self) -> None:
        tool = SqlQueryTool(connector=_StubSqlConnector(["n"], [[1], [2]]), max_rows=10)
        result = await tool.invoke({"query": "SELECT n FROM t"})
        assert result["truncated"] is False
        assert result["row_count"] == 2

    async def test_parameters_passed_through(self) -> None:
        connector = _StubSqlConnector(["n"], [[1]])
        tool = SqlQueryTool(connector=connector)
        await tool.invoke({"query": "SELECT n FROM t WHERE n = ?", "parameters": [1]})
        assert connector.calls[-1][1] == [1]

    async def test_as_tool_result_error_on_write(self) -> None:
        tool = SqlQueryTool(connector=_StubSqlConnector(["n"], [[1]]))
        call = ToolCall(tool_name="sql_query", arguments={"query": "DROP TABLE t"}, call_id="c")
        outcome = await tool.as_tool_result(call)
        assert outcome.status is ToolStatus.ERROR

    def test_rejects_non_connector(self) -> None:
        with pytest.raises(TypeError):
            SqlQueryTool(connector=object())  # type: ignore[arg-type]


class TestSqliteConnector:
    async def test_end_to_end_select(self) -> None:
        connection = sqlite3.connect(":memory:", check_same_thread=False)
        connection.execute("CREATE TABLE t (id int, name text)")
        connection.execute("INSERT INTO t VALUES (1, 'a'), (2, 'b')")
        connection.commit()
        tool = SqlQueryTool(connector=SqliteConnector(connection=connection))
        result = await tool.invoke({"query": "SELECT id, name FROM t ORDER BY id"})
        assert result["columns"] == ["id", "name"]
        assert result["rows"] == [[1, "a"], [2, "b"]]
        connection.close()

    def test_rejects_non_connection(self) -> None:
        with pytest.raises(TypeError):
            SqliteConnector(connection=object())  # type: ignore[arg-type]


class TestAiosqliteConnector:
    async def test_missing_backend_friendly_error(self) -> None:
        connector = AiosqliteConnector(database=":memory:")
        with mock.patch.dict(sys.modules, {"aiosqlite": None}):
            with pytest.raises(ImportError, match=r'pip install "pirn-agents\[sql\]"'):
                await connector.execute("SELECT 1")


class _FakeColumnAwarePool(ColumnAwarePool):
    """Offline ColumnAwarePool double so the service connector runs without a driver."""

    def __init__(self, columns: Sequence[str], rows: Sequence[Sequence[Any]]) -> None:
        self._columns = list(columns)
        self._rows = [list(row) for row in rows]
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetch_columns(
        self, query: str, parameters: Sequence[Any] | None = None
    ) -> tuple[list[str], list[list[Any]]]:
        self.calls.append((query, tuple(parameters or ())))
        return self._columns, [list(row) for row in self._rows]

    async def close(self) -> None:
        return None


class TestSqlServiceConnectorIsASqlConnector:
    """PIR-786: the flagship agents connector must satisfy the tool's interface."""

    def test_declares_the_sql_connector_interface(self) -> None:
        assert issubclass(SqlServiceConnector, SqlConnector) is True

    def test_instance_passes_the_tool_type_check(self) -> None:
        connector = SqlServiceConnector(pool=_FakeColumnAwarePool([], []))
        assert isinstance(connector, SqlConnector)

    async def test_end_to_end_through_the_tool(self) -> None:
        pool = _FakeColumnAwarePool(["id", "name"], [[1, "a"], [2, "b"]])
        connector = SqlServiceConnector(pool=pool)
        tool = SqlQueryTool(connector=connector)

        result = await tool.invoke(
            {"query": "SELECT id, name FROM t WHERE id > ?", "parameters": [0]}
        )

        assert result["columns"] == ["id", "name"]
        assert result["rows"] == [[1, "a"], [2, "b"]]
        assert result["row_count"] == 2
        assert result["truncated"] is False
        assert pool.calls == [("SELECT id, name FROM t WHERE id > ?", (0,))]
        await connector.close()

    async def test_tool_surfaces_connector_read_only_rejection(self) -> None:
        connector = SqlServiceConnector(pool=_FakeColumnAwarePool([], []))
        tool = SqlQueryTool(connector=connector, read_only=False)
        with pytest.raises(ValueError):
            await tool.invoke({"query": "DROP TABLE t"})
        await connector.close()
