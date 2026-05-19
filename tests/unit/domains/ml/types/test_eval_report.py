"""Tests for :class:`EvalMetadata`, :class:`EvalMetrics`, and :class:`EvalReportPayload`."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

from pirn.domains.ml.types.eval_metadata import EvalMetadata
from pirn.domains.ml.types.eval_metrics import EvalMetrics
from pirn.domains.ml.types.eval_report_payload import EvalReportPayload


class TestEvalReport(unittest.TestCase):
    def test_construction_and_audit_dict(self) -> None:
        evaluated_at = datetime(2026, 4, 29, 8, 0, tzinfo=UTC)
        metadata = EvalMetadata(
            model_id="rf:xyz",
            dataset_name="d:test",
            evaluated_at=evaluated_at,
        )
        metrics = EvalMetrics(
            scores={"accuracy": 0.91, "f1": 0.87},
            details={"notes": "ok"},
        )
        report = EvalReportPayload(metadata=metadata, data=metrics)
        assert report.report.model_id == "rf:xyz"
        assert report.report.dataset_name == "d:test"
        assert report.metrics.scores == {"accuracy": 0.91, "f1": 0.87}
        assert report.metrics.details == {"notes": "ok"}
