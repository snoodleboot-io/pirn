"""Tests for SQLiteHistory using real :memory: SQLite."""

from __future__ import annotations

import sqlite3
import unittest
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

from pirn.backends.sqlite.sqlite_history import SQLiteHistory
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
