from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from pirn.core.run_result import RunResult


def _make_result(**overrides) -> RunResult:
    now = datetime.now(UTC)
    defaults = dict(
        run_id="run-abc",
        terminals_requested=["k1"],
        outputs={"k1": 42},
        started_at=now,
        finished_at=now + timedelta(seconds=1),
        dispatcher="LocalDispatcher",
    )
    defaults.update(overrides)
    return RunResult(**defaults)


class TestRunResult(unittest.TestCase):
    def test_minimal_construction(self) -> None:
        result = _make_result()
        self.assertEqual(result.run_id, "run-abc")
        self.assertEqual(result.terminals_requested, ["k1"])
        self.assertEqual(result.outputs, {"k1": 42})
        self.assertEqual(result.skipped, [])
        self.assertEqual(result.exceptions, [])
        self.assertEqual(result.lineage, [])
        self.assertEqual(result.status_events, [])

    def test_succeeded_no_exceptions(self) -> None:
        result = _make_result()
        self.assertTrue(result.succeeded)

    def test_succeeded_false_with_exceptions(self) -> None:
        from pirn.managers.exception_record import ExceptionRecord

        rec = ExceptionRecord(
            run_id="run-abc",
            knot_id="k1",
            exc_type="ValueError",
            message="oops",
            traceback_text="traceback",
        )
        result = _make_result(exceptions=[rec])
        self.assertFalse(result.succeeded)

    def test_duration_seconds(self) -> None:
        now = datetime.now(UTC)
        result = _make_result(
            started_at=now,
            finished_at=now + timedelta(seconds=2.5),
        )
        self.assertAlmostEqual(result.duration_seconds, 2.5, places=2)

    def test_run_path_default(self) -> None:
        result = _make_result()
        self.assertEqual(result.run_path, "")

    def test_parent_fields_default_none(self) -> None:
        result = _make_result()
        self.assertIsNone(result.parent_run_id)
        self.assertIsNone(result.parent_knot_id)

    def test_actor_trigger_environment(self) -> None:
        result = _make_result(actor="user1", trigger="manual", environment={"region": "us-east-1"})
        self.assertEqual(result.actor, "user1")
        self.assertEqual(result.trigger, "manual")
        self.assertEqual(result.environment["region"], "us-east-1")

    def test_frozen(self) -> None:
        result = _make_result()
        with self.assertRaises(Exception):
            result.run_id = "other"
