"""Tests for SQLiteHistory using real :memory: SQLite."""

from __future__ import annotations

import shutil
import sqlite3
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from pirn.backends.sqlite.sqlite_history import SQLiteHistory
from pirn.core.knot_source import KnotSourceRecord
from pirn.core.lineage import KnotLineage


def _now() -> datetime:
    return datetime.now(UTC)


def _make_lineage(
    *,
    run_id: str = "run-1",
    knot_id: str = "knot-a",
    knot_class: str = "pkg.MyKnot",
    output_hash: str | None = "sha256:out",
    parent_input_hashes: dict[str, str] | None = None,
    outcome: str = "ok",
) -> KnotLineage:
    now = _now()
    return KnotLineage(
        run_id=run_id,
        knot_id=knot_id,
        knot_class=knot_class,
        knot_config_hash="cfg-hash",
        output_hash=output_hash,
        parent_input_hashes=parent_input_hashes or {},
        outcome=outcome,
        dispatcher="LocalDispatcher",
        started_at=now,
        finished_at=now,
    )


def _make_run_result(
    *,
    run_id: str = "run-1",
    succeeded: bool = True,
    actor: str | None = "tester",
    trigger: str | None = None,
    parent_run_id: str | None = None,
    parent_knot_id: str | None = None,
    lineage: list[KnotLineage] | None = None,
) -> MagicMock:
    from pirn.core.run_result import RunResult

    now = _now()
    # Build a real RunResult for proper JSON serialization
    result = RunResult(
        run_id=run_id,
        terminals_requested=[],
        outputs={},
        lineage=lineage or [],
        started_at=now,
        finished_at=now,
        dispatcher="LocalDispatcher",
        actor=actor,
        trigger=trigger,
        parent_run_id=parent_run_id,
        parent_knot_id=parent_knot_id,
    )
    return result


class TestSQLiteHistorySchemaInit(unittest.IsolatedAsyncioTestCase):
    """SQLiteHistory creates tables on first use."""

    def setUp(self) -> None:
        self.history = SQLiteHistory(path=":memory:")
        self.addCleanup(self.history.close)

    async def test_tables_created_on_first_use(self) -> None:
        result = _make_run_result()
        await self.history.record_run(result)
        tables = {
            row[0]
            for row in self.history._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        self.assertIn("runs", tables)
        self.assertIn("lineage", tables)

    async def test_schema_version_recorded(self) -> None:
        result = _make_run_result()
        await self.history.record_run(result)
        row = self.history._conn.execute(
            "SELECT version FROM pirn_schema_version WHERE component='history'"
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertGreaterEqual(row[0], 1)


class TestSQLiteHistoryRecordAndQuery(unittest.IsolatedAsyncioTestCase):
    """record_run / get_run / query_lineage_* / query_runs_by_actor."""

    def setUp(self) -> None:
        self.history = SQLiteHistory(path=":memory:")
        self.addCleanup(self.history.close)

    async def test_record_and_get_run_round_trip(self) -> None:
        result = _make_run_result(run_id="run-001")
        await self.history.record_run(result)
        retrieved = await self.history.get_run("run-001")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.run_id, "run-001")

    async def test_get_run_returns_none_for_missing(self) -> None:
        await self.history.record_run(_make_run_result(run_id="r1"))
        result = await self.history.get_run("nonexistent")
        self.assertIsNone(result)

    async def test_record_run_stores_lineage(self) -> None:
        lin = _make_lineage(run_id="run-1", knot_id="k1", output_hash="sha256:out1")
        result = _make_run_result(run_id="run-1", lineage=[lin])
        await self.history.record_run(result)
        records = await self.history.query_lineage_by_output_hash("sha256:out1")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].knot_id, "k1")

    async def test_query_lineage_by_input_hash(self) -> None:
        lin = _make_lineage(
            run_id="run-1",
            knot_id="k2",
            parent_input_hashes={"x": "sha256:inp"},
        )
        result = _make_run_result(run_id="run-1", lineage=[lin])
        await self.history.record_run(result)
        records = await self.history.query_lineage_by_input_hash("sha256:inp")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].knot_id, "k2")

    async def test_query_lineage_by_knot_id(self) -> None:
        lin = _make_lineage(run_id="run-1", knot_id="knot-xyz")
        result = _make_run_result(run_id="run-1", lineage=[lin])
        await self.history.record_run(result)
        records = await self.history.query_lineage_by_knot_id("knot-xyz")
        self.assertEqual(len(records), 1)

    async def test_query_runs_by_actor(self) -> None:
        r1 = _make_run_result(run_id="run-1", actor="alice")
        r2 = _make_run_result(run_id="run-2", actor="bob")
        await self.history.record_run(r1)
        await self.history.record_run(r2)
        alice_runs = await self.history.query_runs_by_actor("alice")
        self.assertEqual(len(alice_runs), 1)
        self.assertEqual(alice_runs[0].run_id, "run-1")

    async def test_children_of_returns_child_runs(self) -> None:
        parent = _make_run_result(run_id="parent-1")
        child = _make_run_result(run_id="child-1", parent_run_id="parent-1")
        await self.history.record_run(parent)
        await self.history.record_run(child)
        children = await self.history.children_of("parent-1")
        self.assertEqual(len(children), 1)
        self.assertEqual(children[0].run_id, "child-1")

    async def test_children_of_returns_empty_for_root_run(self) -> None:
        result = _make_run_result(run_id="run-1")
        await self.history.record_run(result)
        children = await self.history.children_of("run-1")
        self.assertEqual(children, [])

    async def test_lineage_query_returns_empty_for_missing_hash(self) -> None:
        records = await self.history.query_lineage_by_output_hash("sha256:nothere")
        self.assertEqual(records, [])


class TestSQLiteHistorySharedConnection(unittest.IsolatedAsyncioTestCase):
    """SQLiteHistory accepts a pre-built sqlite3.Connection."""

    async def test_shared_connection_persists_across_instances(self) -> None:
        conn = sqlite3.connect(":memory:")
        history1 = SQLiteHistory(connection=conn)
        history2 = SQLiteHistory(connection=conn)
        result = _make_run_result(run_id="shared-run")
        await history1.record_run(result)
        retrieved = await history2.get_run("shared-run")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.run_id, "shared-run")


class _FailingConnection:
    """Delegates to a real connection but raises on the nth ``executemany``.

    ``record_run`` issues an ``INSERT`` followed by two ``executemany`` calls, so
    failing one of the latter reproduces a failure that lands *after* the run row
    has already been written into the open transaction.
    """

    def __init__(self, connection: sqlite3.Connection, *, fail_on_executemany_call: int) -> None:
        self._connection = connection
        self._fail_on_executemany_call = fail_on_executemany_call
        self.executemany_calls = 0

    def __getattr__(self, name: str) -> Any:
        return getattr(self._connection, name)

    def executemany(self, *args: Any, **kwargs: Any) -> Any:
        self.executemany_calls += 1
        if self.executemany_calls == self._fail_on_executemany_call:
            raise RuntimeError("statement failed partway through record_run")
        return self._connection.executemany(*args, **kwargs)


class TestSQLiteHistoryTransactionOwnership(unittest.IsolatedAsyncioTestCase):
    """Writes end only the transaction their own statements opened (PIR-823).

    The class docstring recommends sharing one connection with ``SQLiteStore``,
    so a transaction opened by someone else on that connection is documented
    usage rather than misuse.
    """

    def setUp(self) -> None:
        self._dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self._dir, True)
        self.db_path = str(Path(self._dir) / "pirn.db")

    def _initialised_history(self) -> tuple[sqlite3.Connection, SQLiteHistory]:
        connection = sqlite3.connect(self.db_path)
        history = SQLiteHistory(connection=connection)
        history._ensure_init()
        return connection, history

    async def test_record_run_leaves_a_callers_open_transaction_open(self) -> None:
        connection, history = self._initialised_history()
        self.addCleanup(connection.close)
        connection.execute("CREATE TABLE caller_work (v TEXT)")
        connection.commit()

        connection.execute("INSERT INTO caller_work VALUES ('half-written')")
        self.assertTrue(connection.in_transaction)
        await history.record_run(_make_run_result(run_id="run-1"))
        self.assertTrue(connection.in_transaction)

    async def test_record_knot_source_leaves_a_callers_open_transaction_open(self) -> None:
        connection, history = self._initialised_history()
        self.addCleanup(connection.close)
        connection.execute("CREATE TABLE caller_work (v TEXT)")
        connection.commit()

        connection.execute("INSERT INTO caller_work VALUES ('half-written')")
        await history.record_knot_source(
            KnotSourceRecord(
                source_hash="sha256:src",
                source_text="class K: ...",
                knot_class="pkg.MyKnot",
                pirn_version="0.0.0",
            )
        )
        self.assertTrue(connection.in_transaction)

    async def test_record_run_does_not_make_a_callers_rolled_back_work_durable(self) -> None:
        connection, history = self._initialised_history()
        connection.execute("CREATE TABLE caller_work (v TEXT)")
        connection.commit()

        connection.execute("INSERT INTO caller_work VALUES ('half-written')")
        await history.record_run(_make_run_result(run_id="run-1"))
        connection.rollback()
        connection.close()

        reopened = sqlite3.connect(self.db_path)
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.execute("SELECT v FROM caller_work").fetchall(), [])

    async def test_record_run_commits_the_transaction_it_opened(self) -> None:
        connection = sqlite3.connect(self.db_path)
        history = SQLiteHistory(connection=connection)
        await history.record_run(
            _make_run_result(
                run_id="run-1",
                lineage=[_make_lineage(parent_input_hashes={"a": "sha256:in"})],
            )
        )
        self.assertFalse(connection.in_transaction)
        connection.close()

        reopened = sqlite3.connect(self.db_path)
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.execute("SELECT run_id FROM runs").fetchall(), [("run-1",)])
        self.assertEqual(reopened.execute("SELECT knot_id FROM lineage").fetchall(), [("knot-a",)])

    async def test_record_run_failing_midway_leaves_no_partial_row(self) -> None:
        connection, history = self._initialised_history()
        history._conn = _FailingConnection(connection, fail_on_executemany_call=1)

        with self.assertRaises(RuntimeError):
            await history.record_run(
                _make_run_result(run_id="run-partial", lineage=[_make_lineage()])
            )
        self.assertFalse(connection.in_transaction)
        connection.close()

        reopened = sqlite3.connect(self.db_path)
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.execute("SELECT run_id FROM runs").fetchall(), [])
        self.assertEqual(reopened.execute("SELECT knot_id FROM lineage").fetchall(), [])

    async def test_record_run_failing_on_the_third_statement_leaves_no_partial_row(self) -> None:
        connection, history = self._initialised_history()
        history._conn = _FailingConnection(connection, fail_on_executemany_call=2)

        with self.assertRaises(RuntimeError):
            await history.record_run(
                _make_run_result(
                    run_id="run-partial",
                    lineage=[_make_lineage(parent_input_hashes={"a": "sha256:in"})],
                )
            )
        self.assertFalse(connection.in_transaction)
        connection.close()

        reopened = sqlite3.connect(self.db_path)
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.execute("SELECT run_id FROM runs").fetchall(), [])
        self.assertEqual(reopened.execute("SELECT knot_id FROM lineage").fetchall(), [])

    async def test_get_run_read_issues_no_commit(self) -> None:
        connection, history = self._initialised_history()
        self.addCleanup(connection.close)
        connection.execute("CREATE TABLE caller_work (v TEXT)")
        connection.commit()

        connection.execute("INSERT INTO caller_work VALUES ('uncommitted')")
        await history.get_run("missing")
        self.assertTrue(connection.in_transaction)
