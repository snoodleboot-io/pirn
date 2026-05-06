"""Tests for RunHistory interface contract."""

from __future__ import annotations

import unittest

from pirn.backends.base.run_history import RunHistory


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

    def test_error_message_includes_subclass_name(self) -> None:
        class MyHistory(RunHistory):
            pass

        h = MyHistory()

        import asyncio

        with self.assertRaises(NotImplementedError) as ctx:
            asyncio.run(h.get_run("x"))
        self.assertIn("MyHistory", str(ctx.exception))
