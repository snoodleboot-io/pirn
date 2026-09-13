"""Tests for RunHistory interface contract."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

from pirn.backends.base.run_history import RunHistory
from pirn.core.knot_lineage import KnotLineage


class TestRunHistoryInterface(unittest.IsolatedAsyncioTestCase):
    """RunHistory is an abstract interface; all methods raise NotImplementedError."""

    def _make_history(self) -> RunHistory:
        return RunHistory()

    async def test_record_run_raises_not_implemented(self) -> None:
        h = self._make_history()
        with self.assertRaises(NotImplementedError) as ctx:
            await h.record_run(object())
        self.assertIn("record_run()", str(ctx.exception))

    async def test_get_run_raises_not_implemented(self) -> None:
        h = self._make_history()
        with self.assertRaises(NotImplementedError) as ctx:
            await h.get_run("run-1")
        self.assertIn("get_run()", str(ctx.exception))

    async def test_query_lineage_by_output_hash_raises(self) -> None:
        h = self._make_history()
        with self.assertRaises(NotImplementedError) as ctx:
            await h.query_lineage_by_output_hash("sha256:abc")
        self.assertIn("query_lineage_by_output_hash()", str(ctx.exception))

    async def test_query_lineage_by_input_hash_raises(self) -> None:
        h = self._make_history()
        with self.assertRaises(NotImplementedError) as ctx:
            await h.query_lineage_by_input_hash("sha256:abc")
        self.assertIn("query_lineage_by_input_hash()", str(ctx.exception))

    async def test_query_lineage_by_knot_id_raises(self) -> None:
        h = self._make_history()
        with self.assertRaises(NotImplementedError) as ctx:
            await h.query_lineage_by_knot_id("knot-1")
        self.assertIn("query_lineage_by_knot_id()", str(ctx.exception))

    async def test_query_latest_lineage_by_knot_id_raises(self) -> None:
        h = self._make_history()
        with self.assertRaises(NotImplementedError) as ctx:
            await h.query_latest_lineage_by_knot_id("knot-1")
        self.assertIn("query_latest_lineage_by_knot_id()", str(ctx.exception))

    async def test_query_runs_by_actor_raises(self) -> None:
        h = self._make_history()
        with self.assertRaises(NotImplementedError) as ctx:
            await h.query_runs_by_actor("actor-1")
        self.assertIn("query_runs_by_actor()", str(ctx.exception))

    async def test_children_of_raises_not_implemented(self) -> None:
        h = self._make_history()
        with self.assertRaises(NotImplementedError) as ctx:
            await h.children_of("run-1")
        self.assertIn("children_of()", str(ctx.exception))

    async def test_query_latest_lineage_by_knot_id_delegates_and_raises(self) -> None:
        """The default implementation delegates to query_lineage_by_knot_id."""
        h = self._make_history()
        with self.assertRaises(NotImplementedError) as ctx:
            await h.query_latest_lineage_by_knot_id("knot-1")
        self.assertIn("query_lineage_by_knot_id()", str(ctx.exception))


class TestRunHistoryDefaultLatestLineage(unittest.IsolatedAsyncioTestCase):
    """The default query_latest_lineage_by_knot_id picks the max by finished_at."""

    @staticmethod
    def _lineage(knot_id: str, output_hash: str, finished_at: datetime) -> KnotLineage:
        return KnotLineage(
            run_id=f"run-{output_hash}",
            knot_id=knot_id,
            knot_class="pkg.MyKnot",
            knot_config_hash="cfg",
            output_hash=output_hash,
            outcome="ok",
            dispatcher="LocalDispatcher",
            started_at=finished_at,
            finished_at=finished_at,
            # pyright does not resolve KnotLineage's Field(None, ...)
            # positional-None defaults as optional -- pass explicitly (same
            # workaround used across the backend history test suites).
            error_record_id=None,
            skip_reason=None,
        )

    async def test_returns_the_row_with_the_greatest_finished_at(self) -> None:
        rows = [
            self._lineage("k", "sha256:v1", datetime(2026, 1, 1, tzinfo=UTC)),
            self._lineage("k", "sha256:v3", datetime(2026, 6, 1, tzinfo=UTC)),
            self._lineage("k", "sha256:v2", datetime(2026, 3, 1, tzinfo=UTC)),
        ]

        class _FixedHistory(RunHistory):
            async def query_lineage_by_knot_id(self, knot_id: str) -> list[KnotLineage]:
                return rows

        latest = await _FixedHistory().query_latest_lineage_by_knot_id("k")

        assert latest is not None
        assert latest.output_hash == "sha256:v3"

    async def test_returns_none_when_no_rows(self) -> None:
        class _EmptyHistory(RunHistory):
            async def query_lineage_by_knot_id(self, knot_id: str) -> list[KnotLineage]:
                return []

        latest = await _EmptyHistory().query_latest_lineage_by_knot_id("k")

        assert latest is None

    def test_error_message_includes_subclass_name(self) -> None:
        class MyHistory(RunHistory):
            pass

        h = MyHistory()

        import asyncio

        with self.assertRaises(NotImplementedError) as ctx:
            asyncio.run(h.get_run("x"))
        self.assertIn("MyHistory", str(ctx.exception))
