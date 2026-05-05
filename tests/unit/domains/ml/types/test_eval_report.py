"""Tests for :class:`EvalReport`."""

from __future__ import annotations

from datetime import datetime, timezone
import unittest

from pirn.domains.ml.types.eval_report import EvalReport


class TestEvalReport(unittest.TestCase):
    def test_construction_and_audit_dict(self) -> None:
        evaluated_at = datetime(2026, 4, 29, 8, 0, tzinfo=timezone.utc)
        report = EvalReport(
            model_id="rf:xyz",
            metrics={"accuracy": 0.91, "f1": 0.87},
            dataset_name="d:test",
            evaluated_at=evaluated_at,
            details={"notes": "ok"},
        )
        audit = report._pirn_audit_dict()
        assert audit == {
            "model_id": "rf:xyz",
            "dataset_name": "d:test",
            "metrics": {"accuracy": 0.91, "f1": 0.87},
            "details": {"notes": "ok"},
            "evaluated_at": evaluated_at.isoformat(),
        }
