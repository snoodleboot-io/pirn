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
from pirn_agents.tools.sql import aiosqlite_connector
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


class TestSqliteConnectorDurability:
    """Regression (PIR-807): a write through the stdlib connector must persist.

    ``_execute_sync`` ran the statement and closed only the cursor, so under
    sqlite3's default ``isolation_level`` the implicit transaction an ``INSERT``
    opened was never committed. The connection is *caller-owned* and long-lived,
    so the loss was not immediately visible — it surfaced whenever the caller
    closed without committing, and any concurrent connection never saw the row.

    The fix mirrors PIR-801's transaction ownership: commit exactly the
    transaction this call opened, roll it back when the statement raises, and
    never touch one the caller already had open.
    """

    @staticmethod
    def _rows_on_disk(database: str) -> list[tuple[Any, ...]]:
        """Read ``widget`` back on a separate connection — the durable truth."""
        with sqlite3.connect(database) as disk:
            return disk.execute("SELECT id, name FROM widget ORDER BY id").fetchall()

    async def test_a_write_is_visible_to_another_connection(self, tmp_path: Any) -> None:
        database = str(tmp_path / "durable.db")
        connection = sqlite3.connect(database, check_same_thread=False)
        connector = SqliteConnector(connection=connection)
        try:
            await connector.execute("CREATE TABLE widget (id INTEGER PRIMARY KEY, name TEXT)")
            await connector.execute("INSERT INTO widget (id, name) VALUES (?, ?)", (1, "sprocket"))
            # No connection.commit() here: the connector owes the commit for the
            # transaction its own INSERT opened.
            assert self._rows_on_disk(database) == [(1, "sprocket")]
        finally:
            connection.close()

    async def test_an_update_and_delete_persist(self, tmp_path: Any) -> None:
        database = str(tmp_path / "mutate.db")
        connection = sqlite3.connect(database, check_same_thread=False)
        connector = SqliteConnector(connection=connection)
        try:
            await connector.execute("CREATE TABLE widget (id INTEGER PRIMARY KEY, name TEXT)")
            await connector.execute("INSERT INTO widget (id, name) VALUES (1, 'old')")
            await connector.execute("INSERT INTO widget (id, name) VALUES (2, 'doomed')")
            await connector.execute("UPDATE widget SET name = ? WHERE id = ?", ("new", 1))
            await connector.execute("DELETE FROM widget WHERE id = ?", (2,))
            assert self._rows_on_disk(database) == [(1, "new")]
        finally:
            connection.close()

    async def test_a_failed_statement_leaves_no_residue(self, tmp_path: Any) -> None:
        database = str(tmp_path / "residue.db")
        connection = sqlite3.connect(database, check_same_thread=False)
        connector = SqliteConnector(connection=connection)
        try:
            await connector.execute(
                "CREATE TABLE widget (id INTEGER PRIMARY KEY, name TEXT UNIQUE)"
            )
            for row_id, name in ((1, "a"), (2, "b"), (3, "c")):
                await connector.execute(
                    "INSERT INTO widget (id, name) VALUES (?, ?)", (row_id, name)
                )

            # ``UPDATE OR FAIL`` renames row 1, then hits the UNIQUE constraint on
            # row 2 and aborts — keeping row 1's change and leaving the transaction
            # open. Skipping the commit is not enough; it must be rolled back or the
            # next statement inherits the partial write.
            with pytest.raises(sqlite3.IntegrityError):
                await connector.execute("UPDATE OR FAIL widget SET name = 'dup'")
            assert connection.in_transaction is False

            # An innocent read must not adopt — nor commit — the residue.
            await connector.execute("SELECT id FROM widget")
            assert self._rows_on_disk(database) == [(1, "a"), (2, "b"), (3, "c")]
        finally:
            connection.close()

    async def test_a_caller_transaction_is_left_alone(self, tmp_path: Any) -> None:
        database = str(tmp_path / "caller_txn.db")
        connection = sqlite3.connect(database, check_same_thread=False)
        connector = SqliteConnector(connection=connection)
        try:
            await connector.execute("CREATE TABLE widget (id INTEGER PRIMARY KEY, name TEXT)")
            await connector.execute("INSERT INTO widget (id, name) VALUES (1, 'a')")

            # The caller owns the connection and may drive it directly; a
            # transaction they opened is theirs to end.
            connection.execute("INSERT INTO widget (id, name) VALUES (2, 'b')")
            assert connection.in_transaction is True

            await connector.execute("SELECT id FROM widget")
            assert connection.in_transaction is True, "the read committed the caller's transaction"

            connection.rollback()
            assert self._rows_on_disk(database) == [(1, "a")]
        finally:
            connection.close()


class _FakeSqliteCursor:
    def __init__(self, columns: Sequence[str], rows: Sequence[Sequence[Any]]) -> None:
        self.description = [(name,) for name in columns]
        self._rows = rows

    async def fetchall(self) -> Sequence[Sequence[Any]]:
        return self._rows

    async def close(self) -> None:
        return None


class _ExplodingSqliteCursor(_FakeSqliteCursor):
    async def fetchall(self) -> Sequence[Sequence[Any]]:
        raise RuntimeError("backend blew up mid-statement")


class _FakeAiosqliteConnection:
    """A double modelling sqlite3's implicit-transaction rule.

    ``sqlite3`` opens a transaction for DML only — not for reads or DDL — and
    ``in_transaction`` reports it. :class:`AiosqliteConnector` reads that flag to
    decide whether it owes a commit (PIR-807), so the double must carry it or the
    real code path is never exercised.
    """

    def __init__(
        self, columns: Sequence[str], rows: Sequence[Sequence[Any]], *, explode: bool = False
    ) -> None:
        self._columns = columns
        self._rows = rows
        self._explode = explode
        self.calls: list[tuple[str, tuple[Any, ...]]] = []
        self.commits = 0
        self.rollbacks = 0
        self.closed = False
        self.in_transaction = False

    async def execute(self, query: str, parameters: tuple[Any, ...]) -> _FakeSqliteCursor:
        self.calls.append((query, parameters))
        if query.lstrip().split(" ")[0].upper() in ("INSERT", "UPDATE", "DELETE", "REPLACE"):
            self.in_transaction = True
        if self._explode:
            return _ExplodingSqliteCursor(self._columns, self._rows)
        return _FakeSqliteCursor(self._columns, self._rows)

    async def commit(self) -> None:
        self.commits += 1
        self.in_transaction = False

    async def rollback(self) -> None:
        self.rollbacks += 1
        self.in_transaction = False

    async def __aenter__(self) -> _FakeAiosqliteConnection:
        return self

    async def __aexit__(self, *_exc: Any) -> None:
        self.closed = True


class _FakeAiosqliteModule:
    """Stands in for the lazily imported ``aiosqlite`` backend."""

    def __init__(self, connection: _FakeAiosqliteConnection) -> None:
        self._connection = connection
        self.databases: list[str] = []

    def connect(self, database: str) -> _FakeAiosqliteConnection:
        self.databases.append(database)
        return self._connection


class TestAiosqliteConnector:
    async def test_missing_backend_friendly_error(self) -> None:
        connector = AiosqliteConnector(database=":memory:")
        with mock.patch.dict(sys.modules, {"aiosqlite": None}):
            with pytest.raises(ImportError, match=r'pip install "pirn-agents\[sql\]"'):
                await connector.execute("SELECT 1")


class TestAiosqliteConnectorDurability:
    """Regression (PIR-807): every write through this connector was discarded.

    ``execute`` opened a connection per query, ran the statement, and let the
    ``async with`` close it without committing. sqlite3 autocommits DDL but opens
    an implicit transaction for DML, so a ``CREATE TABLE`` survived while the
    ``INSERT`` vanished — a reopened database showed the full schema and zero
    rows, with no error at any point.

    The fix mirrors PIR-801's transaction ownership. The connection is opened
    here and never shared, so ``in_transaction`` *is* ownership — nothing else
    could have opened one — and the same three outcomes follow: a write is
    committed, a statement that raises is rolled back, and a read or DDL opens no
    transaction and so issues neither.
    """

    @staticmethod
    def _rows_on_disk(database: str) -> list[tuple[Any, ...]]:
        """Read ``widget`` back with plain sqlite3 — the durable truth."""
        with sqlite3.connect(database) as disk:
            return disk.execute("SELECT id, name FROM widget ORDER BY id").fetchall()

    async def test_a_write_survives_the_per_query_connection(self, tmp_path: Any) -> None:
        pytest.importorskip("aiosqlite")
        database = str(tmp_path / "durable.db")
        connector = AiosqliteConnector(database=database)

        await connector.execute("CREATE TABLE widget (id INTEGER PRIMARY KEY, name TEXT)")
        await connector.execute("INSERT INTO widget (id, name) VALUES (?, ?)", (1, "sprocket"))

        # Each execute opens its own connection, so this read already crosses the
        # close/reopen boundary that used to swallow the row.
        columns, rows = await connector.execute("SELECT id, name FROM widget")
        assert columns == ["id", "name"]
        assert rows == [[1, "sprocket"]]
        assert self._rows_on_disk(database) == [(1, "sprocket")]

    async def test_an_update_and_delete_persist(self, tmp_path: Any) -> None:
        pytest.importorskip("aiosqlite")
        database = str(tmp_path / "mutate.db")
        connector = AiosqliteConnector(database=database)

        await connector.execute("CREATE TABLE widget (id INTEGER PRIMARY KEY, name TEXT)")
        await connector.execute("INSERT INTO widget (id, name) VALUES (1, 'old')")
        await connector.execute("INSERT INTO widget (id, name) VALUES (2, 'doomed')")
        await connector.execute("UPDATE widget SET name = ? WHERE id = ?", ("new", 1))
        await connector.execute("DELETE FROM widget WHERE id = ?", (2,))

        assert self._rows_on_disk(database) == [(1, "new")]

    async def test_a_write_through_the_tool_persists(self, tmp_path: Any) -> None:
        # The reachable path: SqlQueryTool(read_only=False) -> AiosqliteConnector.
        pytest.importorskip("aiosqlite")
        database = str(tmp_path / "via_tool.db")
        tool = SqlQueryTool(connector=AiosqliteConnector(database=database), read_only=False)

        await tool.invoke({"query": "CREATE TABLE widget (id INTEGER PRIMARY KEY, name TEXT)"})
        await tool.invoke(
            {"query": "INSERT INTO widget (id, name) VALUES (?, ?)", "parameters": [1, "kept"]}
        )

        assert self._rows_on_disk(database) == [(1, "kept")]

    async def test_a_write_commits(self) -> None:
        connection = _FakeAiosqliteConnection(["id"], [[1]])
        connector = AiosqliteConnector(database=":memory:")
        with mock.patch.object(
            aiosqlite_connector, "_require", return_value=_FakeAiosqliteModule(connection)
        ):
            await connector.execute("INSERT INTO t (id) VALUES (?)", [1])
        assert (connection.commits, connection.rollbacks) == (1, 0)

    async def test_a_failed_statement_is_rolled_back_not_committed(self) -> None:
        connection = _FakeAiosqliteConnection(["id"], [[1]], explode=True)
        connector = AiosqliteConnector(database=":memory:")
        with mock.patch.object(
            aiosqlite_connector, "_require", return_value=_FakeAiosqliteModule(connection)
        ):
            with pytest.raises(RuntimeError, match="blew up"):
                await connector.execute("INSERT INTO t (id) VALUES (?)", [1])
        assert (connection.commits, connection.rollbacks) == (0, 1)

    @pytest.mark.parametrize("query", ["SELECT id FROM t", "CREATE TABLE t (id INTEGER)"])
    async def test_a_read_or_ddl_neither_commits_nor_rolls_back(self, query: str) -> None:
        # A COMMIT is not merely redundant here: under journal_mode=DELETE it must
        # take the exclusive lock, so a read that issued one could fail with
        # "database is locked" against a concurrent reader.
        connection = _FakeAiosqliteConnection(["id"], [[1]])
        connector = AiosqliteConnector(database=":memory:")
        with mock.patch.object(
            aiosqlite_connector, "_require", return_value=_FakeAiosqliteModule(connection)
        ):
            await connector.execute(query)
        assert (connection.commits, connection.rollbacks) == (0, 0)


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
