"""Tests for DuckDBHistory."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

from pirn.backends.duckdb import DuckDBHistory
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
    lineage: list[KnotLineage] | None = None,
    actor: str | None = "tester",
):
    from pirn.core.run_result import RunResult

    now = _now()
    return RunResult(
        run_id=run_id,
        terminals_requested=[],
        outputs={},
        lineage=lineage or [],
        started_at=now,
        finished_at=now,
        dispatcher="LocalDispatcher",
        actor=actor,
    )


def _make_history() -> DuckDBHistory:
    try:
        return DuckDBHistory(path=":memory:")
    except ImportError:
        raise unittest.SkipTest("duckdb not installed")


class TestDuckDBHistoryInit(unittest.IsolatedAsyncioTestCase):
    async def test_tables_created_on_first_use(self) -> None:
        history = _make_history()
        await history.record_run(_make_run_result())
        tables = {
            row[0]
            for row in history._conn.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
            ).fetchall()
        }
        self.assertIn("runs", tables)
        self.assertIn("lineage", tables)


class TestDuckDBHistoryCRUD(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.history = _make_history()

    async def test_record_and_get_run(self) -> None:
        result = _make_run_result(run_id="run-001")
        await self.history.record_run(result)
        retrieved = await self.history.get_run("run-001")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.run_id, "run-001")

    async def test_get_run_returns_none_for_missing(self) -> None:
        retrieved = await self.history.get_run("nonexistent")
        self.assertIsNone(retrieved)

    async def test_query_lineage_by_output_hash(self) -> None:
        lin = _make_lineage(run_id="run-1", knot_id="k1", output_hash="sha256:out1")
        await self.history.record_run(_make_run_result(run_id="run-1", lineage=[lin]))
        records = await self.history.query_lineage_by_output_hash("sha256:out1")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].knot_id, "k1")

    async def test_query_lineage_by_input_hash(self) -> None:
        lin = _make_lineage(
            run_id="run-1",
            knot_id="k2",
            parent_input_hashes={"x": "sha256:inp"},
        )
        await self.history.record_run(_make_run_result(run_id="run-1", lineage=[lin]))
        records = await self.history.query_lineage_by_input_hash("sha256:inp")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].knot_id, "k2")

    async def test_query_lineage_by_knot_id(self) -> None:
        lin = _make_lineage(run_id="run-1", knot_id="k-xyz")
        await self.history.record_run(_make_run_result(run_id="run-1", lineage=[lin]))
        records = await self.history.query_lineage_by_knot_id("k-xyz")
        self.assertEqual(len(records), 1)

    async def test_query_runs_by_actor(self) -> None:
        r1 = _make_run_result(run_id="run-1", actor="alice")
        r2 = _make_run_result(run_id="run-2", actor="bob")
        await self.history.record_run(r1)
        await self.history.record_run(r2)
        runs = await self.history.query_runs_by_actor("alice")
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0].run_id, "run-1")

    async def test_query_lineage_by_class(self) -> None:
        lin = _make_lineage(run_id="run-1", knot_id="k1", knot_class="pkg.SpecialKnot")
        await self.history.record_run(_make_run_result(run_id="run-1", lineage=[lin]))
        records = await self.history.query_lineage_by_class("pkg.SpecialKnot")
        self.assertEqual(len(records), 1)

    async def test_run_count(self) -> None:
        await self.history.record_run(_make_run_result(run_id="r1"))
        await self.history.record_run(_make_run_result(run_id="r2"))
        count = await self.history.run_count()
        self.assertEqual(count, 2)

    async def test_run_count_empty(self) -> None:
        count = await self.history.run_count()
        self.assertEqual(count, 0)

    async def test_query_returns_empty_for_missing_hash(self) -> None:
        records = await self.history.query_lineage_by_output_hash("sha256:nothere")
        self.assertEqual(records, [])


class TestDuckDBHistoryInheritance(unittest.TestCase):
    def test_is_run_history(self) -> None:
        from pirn.backends.base.run_history import RunHistory

        history = _make_history()
        self.assertIsInstance(history, RunHistory)
