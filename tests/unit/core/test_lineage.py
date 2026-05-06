from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from pirn.core.lineage import KnotLineage


def _make_lineage(**overrides) -> KnotLineage:
    now = datetime.now(UTC)
    defaults = dict(
        run_id="run-abc",
        knot_id="k1",
        knot_class="pkg.K1",
        knot_config_hash="sha256:deadbeef",
        outcome="ok",
        dispatcher="LocalDispatcher",
        started_at=now,
        finished_at=now + timedelta(milliseconds=100),
    )
    defaults.update(overrides)
    return KnotLineage(**defaults)


class TestKnotLineage(unittest.TestCase):
    def test_minimal_construction(self) -> None:
        rec = _make_lineage()
        self.assertEqual(rec.run_id, "run-abc")
        self.assertEqual(rec.knot_id, "k1")
        self.assertEqual(rec.outcome, "ok")
        self.assertEqual(rec.parent_input_hashes, {})
        self.assertIsNone(rec.output_hash)
        self.assertIsNone(rec.error_record_id)
        self.assertIsNone(rec.skip_reason)
        self.assertEqual(rec.extra, {})

    def test_succeeded_ok(self) -> None:
        rec = _make_lineage(outcome="ok")
        self.assertTrue(rec.succeeded)

    def test_succeeded_err(self) -> None:
        rec = _make_lineage(outcome="err")
        self.assertFalse(rec.succeeded)

    def test_succeeded_skipped(self) -> None:
        rec = _make_lineage(outcome="skipped")
        self.assertFalse(rec.succeeded)

    def test_duration_ms(self) -> None:
        now = datetime.now(UTC)
        rec = _make_lineage(
            started_at=now,
            finished_at=now + timedelta(milliseconds=200),
        )
        self.assertAlmostEqual(rec.duration_ms, 200.0, places=0)

    def test_parent_input_hashes(self) -> None:
        rec = _make_lineage(parent_input_hashes={"a": "sha256:aaa", "b": "sha256:bbb"})
        self.assertEqual(rec.parent_input_hashes["a"], "sha256:aaa")

    def test_error_outcome_fields(self) -> None:
        rec = _make_lineage(outcome="err", error_record_id="exc-001")
        self.assertEqual(rec.error_record_id, "exc-001")

    def test_skip_reason(self) -> None:
        rec = _make_lineage(outcome="skipped", skip_reason="parent failed")
        self.assertEqual(rec.skip_reason, "parent failed")

    def test_extra_metadata(self) -> None:
        rec = _make_lineage(extra={"element_index": 3})
        self.assertEqual(rec.extra["element_index"], 3)

    def test_frozen(self) -> None:
        rec = _make_lineage()
        with self.assertRaises(Exception):
            rec.outcome = "err"
