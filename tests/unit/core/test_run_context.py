from __future__ import annotations

import unittest

from pirn.core.run_context import RunContext
from pirn.core.lineage import KnotLineage


class TestRunContext(unittest.TestCase):
    def _make_context(self, **kwargs) -> RunContext:
        defaults = dict(
            run_id="run-test",
            terminals_requested=["k1"],
            dispatcher_name="LocalDispatcher",
        )
        defaults.update(kwargs)
        return RunContext(**defaults)

    def test_basic_construction(self) -> None:
        ctx = self._make_context()
        self.assertEqual(ctx.run_id, "run-test")
        self.assertEqual(ctx.terminals_requested, ["k1"])
        self.assertEqual(ctx.dispatcher_name, "LocalDispatcher")
        self.assertEqual(ctx.parameters, {})
        self.assertEqual(ctx.lineage, [])
        self.assertEqual(ctx.skipped, [])
        self.assertIsNone(ctx.actor)
        self.assertIsNone(ctx.trigger)
        self.assertIsNone(ctx.parent_run_id)
        self.assertIsNone(ctx.parent_knot_id)

    def test_parameters_stored(self) -> None:
        ctx = self._make_context(parameters={"x": 1})
        self.assertEqual(ctx.parameters["x"], 1)

    def test_none_parameters_defaults_to_empty(self) -> None:
        ctx = self._make_context(parameters=None)
        self.assertEqual(ctx.parameters, {})

    def test_hostname_in_environment(self) -> None:
        ctx = self._make_context()
        self.assertIn("hostname", ctx.environment)

    def test_environment_merged(self) -> None:
        ctx = self._make_context(environment={"region": "us-east-1"})
        self.assertEqual(ctx.environment["region"], "us-east-1")
        self.assertIn("hostname", ctx.environment)

    def test_runtime_info_populated(self) -> None:
        ctx = self._make_context()
        self.assertIn("python_version", ctx.runtime_info)
        self.assertIn("pirn_version", ctx.runtime_info)
        self.assertIn("platform", ctx.runtime_info)

    def test_add_lineage(self) -> None:
        from datetime import UTC, datetime

        ctx = self._make_context()
        now = datetime.now(UTC)
        record = KnotLineage(
            run_id="run-test",
            knot_id="k1",
            knot_class="TestKnot",
            knot_config_hash="sha256:abc",
            outcome="ok",
            dispatcher="LocalDispatcher",
            started_at=now,
            finished_at=now,
        )
        ctx.add_lineage(record)
        self.assertEqual(len(ctx.lineage), 1)
        self.assertIs(ctx.lineage[0], record)

    def test_finalize_produces_run_result(self) -> None:
        ctx = self._make_context(actor="alice", trigger="manual")
        result = ctx.finalize(outputs={"k1": 99})
        self.assertEqual(result.run_id, "run-test")
        self.assertEqual(result.outputs["k1"], 99)
        self.assertEqual(result.dispatcher, "LocalDispatcher")
        self.assertEqual(result.run_path, "/run-test")
        self.assertEqual(result.actor, "alice")
        self.assertEqual(result.trigger, "manual")
        self.assertTrue(result.succeeded)

    def test_finalize_run_path_set(self) -> None:
        ctx = self._make_context()
        result = ctx.finalize({})
        self.assertEqual(result.run_path, "/run-test")

    def test_finalize_parent_fields_propagated(self) -> None:
        ctx = self._make_context(parent_run_id="parent-run", parent_knot_id="sub-knot")
        result = ctx.finalize({})
        self.assertEqual(result.parent_run_id, "parent-run")
        self.assertEqual(result.parent_knot_id, "sub-knot")
