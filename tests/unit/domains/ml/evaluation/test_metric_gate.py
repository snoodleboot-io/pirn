"""Tests for :class:`MetricGate`."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.evaluation.metric_gate import MetricGate
from pirn.domains.ml.types.eval_report import EvalReport
from pirn.tapestry import Tapestry


def _report(value: float) -> EvalReport:
    return EvalReport(
        model_id="m1",
        metrics={"accuracy": value},
        dataset_name="d:test",
        evaluated_at=datetime.now(timezone.utc),
    )


@knot
async def emit_passing_report() -> EvalReport:
    return _report(0.95)


@knot
async def emit_failing_report() -> EvalReport:
    return _report(0.10)


class TestMetricGateHappyPath:
    async def test_passes_when_metric_meets_threshold(self) -> None:
        with Tapestry() as t:
            report = emit_passing_report(_config=KnotConfig(id="report"))
            MetricGate(
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
            MetricGate(
                report=report,
                metric="accuracy",
                min_value=0.9,
                _config=KnotConfig(id="gate"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["gate"] is False


class TestMetricGateConstruction:
    def test_rejects_empty_metric(self) -> None:
        with Tapestry():
            report = emit_passing_report(_config=KnotConfig(id="report"))
            with pytest.raises(ValueError, match="metric must be"):
                MetricGate(
                    report=report,
                    metric="",
                    min_value=0.0,
                    _config=KnotConfig(id="bad"),
                )
