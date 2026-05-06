"""Tests for InMemoryHistory."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime
from unittest.mock import MagicMock

from pirn.backends.in_memory.in_memory_history import InMemoryHistory
from pirn.core.lineage import KnotLineage


def _make_lineage(
    *,
    run_id: str = "run-1",
    knot_id: str = "knot-a",
    knot_class: str = "MyKnot",
    knot_config_hash: str = "cfg-hash",
    output_hash: str | None = "sha256:out",
    parent_input_hashes: dict[str, str] | None = None,
    outcome: str = "ok",
) -> KnotLineage:
    now = datetime.now(UTC)
    return KnotLineage(
        run_id=run_id,
        knot_id=knot_id,
        knot_class=knot_class,
        knot_config_hash=knot_config_hash,
        output_hash=output_hash,
        parent_input_hashes=parent_input_hashes or {},
        outcome=outcome,
        dispatcher="LocalDispatcher",
        started_at=now,
        finished_at=now,
    )


def _make_result(
    *,
    run_id: str = "run-1",
    actor: str | None = None,
    parent_run_id: str | None = None,
    lineage: list[KnotLineage] | None = None,
) -> MagicMock:
    result = MagicMock()
    result.run_id = run_id
    result.actor = actor
    result.parent_run_id = parent_run_id
    result.lineage = lineage or []
    return result


class TestInMemoryHistory(unittest.IsolatedAsyncioTestCase):
    """InMemoryHistory: record/query semantics for runs and lineage."""

    def setUp(self) -> None:
        self.history = InMemoryHistory()

    async def test_get_run_returns_none_for_missing(self) -> None:
        result = await self.history.get_run("nonexistent")
        self.assertIsNone(result)

    async def test_record_and_get_run(self) -> None:
        result = _make_result(run_id="run-1")
        await self.history.record_run(result)
        retrieved = await self.history.get_run("run-1")
        self.assertIs(retrieved, result)

    async def test_record_run_indexes_by_actor(self) -> None:
        result = _make_result(run_id="run-1", actor="user-a")
        await self.history.record_run(result)
        runs = await self.history.query_runs_by_actor("user-a")
        self.assertEqual(len(runs), 1)
        self.assertIs(runs[0], result)

    async def test_query_runs_by_actor_empty_for_unknown(self) -> None:
        runs = await self.history.query_runs_by_actor("nobody")
        self.assertEqual(runs, [])

    async def test_record_run_without_actor_not_indexed_by_actor(self) -> None:
        result = _make_result(run_id="run-1", actor=None)
        await self.history.record_run(result)
        self.assertEqual(await self.history.query_runs_by_actor("nobody"), [])

    async def test_children_of_returns_empty_for_no_children(self) -> None:
        children = await self.history.children_of("run-1")
        self.assertEqual(children, [])

    async def test_children_of_returns_child_runs(self) -> None:
        parent = _make_result(run_id="parent-1")
        child = _make_result(run_id="child-1", parent_run_id="parent-1")
        await self.history.record_run(parent)
        await self.history.record_run(child)
        children = await self.history.children_of("parent-1")
        self.assertIn(child, children)

    async def test_lineage_indexed_by_output_hash(self) -> None:
        lin = _make_lineage(run_id="run-1", knot_id="k1", output_hash="sha256:out1")
        result = _make_result(run_id="run-1", lineage=[lin])
        await self.history.record_run(result)
        records = await self.history.query_lineage_by_output_hash("sha256:out1")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].knot_id, "k1")

    async def test_lineage_indexed_by_input_hash(self) -> None:
        lin = _make_lineage(
            run_id="run-1",
            knot_id="k2",
            parent_input_hashes={"x": "sha256:inp"},
        )
        result = _make_result(run_id="run-1", lineage=[lin])
        await self.history.record_run(result)
        records = await self.history.query_lineage_by_input_hash("sha256:inp")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].knot_id, "k2")

    async def test_lineage_indexed_by_knot_id(self) -> None:
        lin = _make_lineage(run_id="run-1", knot_id="knot-xyz")
        result = _make_result(run_id="run-1", lineage=[lin])
        await self.history.record_run(result)
        records = await self.history.query_lineage_by_knot_id("knot-xyz")
        self.assertEqual(len(records), 1)

    async def test_lineage_without_output_hash_not_indexed_by_output(self) -> None:
        lin = _make_lineage(run_id="run-1", knot_id="k3", output_hash=None, outcome="err")
        result = _make_result(run_id="run-1", lineage=[lin])
        await self.history.record_run(result)
        records = await self.history.query_lineage_by_output_hash("sha256:none")
        self.assertEqual(records, [])

    async def test_query_returns_copy_not_internal_list(self) -> None:
        lin = _make_lineage(run_id="run-1", knot_id="k1")
        result = _make_result(run_id="run-1", lineage=[lin])
        await self.history.record_run(result)
        records = await self.history.query_lineage_by_knot_id("k1")
        records.clear()
        # Subsequent query still returns data
        records2 = await self.history.query_lineage_by_knot_id("k1")
        self.assertEqual(len(records2), 1)

    async def test_multiple_runs_same_actor(self) -> None:
        r1 = _make_result(run_id="run-1", actor="alice")
        r2 = _make_result(run_id="run-2", actor="alice")
        await self.history.record_run(r1)
        await self.history.record_run(r2)
        runs = await self.history.query_runs_by_actor("alice")
        self.assertEqual(len(runs), 2)
