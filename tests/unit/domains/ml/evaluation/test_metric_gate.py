"""Tests for :class:`MetricCheck`."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.evaluation.metric_gate import MetricCheck
from pirn.domains.ml.types.eval_metadata import EvalMetadata
from pirn.domains.ml.types.eval_metrics import EvalMetrics
from pirn.domains.ml.types.eval_report_payload import EvalReportPayload
from pirn.tapestry import Tapestry


def _report(value: float) -> EvalReportPayload:
    return EvalReportPayload(
        metadata=EvalMetadata(
            model_id="m1",
            dataset_name="d:test",
            evaluated_at=datetime.now(UTC),
        ),
        data=EvalMetrics(scores={"accuracy": value}),
    )


@knot
async def emit_passing_report() -> EvalReportPayload:
    return _report(0.95)


@knot
async def emit_failing_report() -> EvalReportPayload:
    return _report(0.10)


class TestMetricCheckHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_passes_when_metric_meets_threshold(self) -> None:
        with Tapestry() as t:
            report = emit_passing_report(_config=KnotConfig(id="report"))
            MetricCheck(
                report=report,
                metric="accuracy",
                min_value=0.9,
                _config=KnotConfig(id="gate"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["gate"] is True

    async def test_returns_false_when_below_threshold(self) -> None:
        with Tapestry() as t:
            report = emit_failing_report(_config=KnotConfig(id="report"))
            MetricCheck(
                report=report,
                metric="accuracy",
                min_value=0.9,
                _config=KnotConfig(id="gate"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["gate"] is False


class TestMetricCheckProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_metric(self) -> None:
        checker = MetricCheck.__new__(MetricCheck)
        object.__setattr__(checker, "_config", KnotConfig(id="x"))
        report = _report(0.95)
        with self.assertRaisesRegex(ValueError, "metric must be"):
            await checker.process(report=report, metric="", min_value=0.0)

    async def test_raises_key_error_for_missing_metric(self) -> None:
        checker = MetricCheck.__new__(MetricCheck)
        object.__setattr__(checker, "_config", KnotConfig(id="x"))
        report = _report(0.95)
        with self.assertRaises(KeyError):
            await checker.process(report=report, metric="missing_key", min_value=0.5)

    async def test_raises_value_error_when_raise_on_fail_set(self) -> None:
        checker = MetricCheck.__new__(MetricCheck)
        object.__setattr__(checker, "_config", KnotConfig(id="x"))
        report = _report(0.10)
        with self.assertRaisesRegex(ValueError, "below threshold"):
            await checker.process(
                report=report, metric="accuracy", min_value=0.9, raise_on_fail=True
            )
