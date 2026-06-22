"""Tests for :class:`ActiveLearningLoop`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_ml.specializations.task_pipelines.active_learning_loop import (
    ActiveLearningLoop,
)
from pirn_ml.types.eval_report_payload import EvalReportPayload

from tests._stubs.recording_database_pool import (
    RecordingDatabasePool,
)


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_zero_n_rounds(self) -> None:
        with Tapestry():
            k = ActiveLearningLoop.__new__(ActiveLearningLoop)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                pool=RecordingDatabasePool(rows=[(1.0, 0)]),
                query="SELECT 1",
                target_column="y",
                feature_names=("a",),
                n_rounds=0,
            )

    async def test_rejects_empty_feature_names(self) -> None:
        with Tapestry():
            k = ActiveLearningLoop.__new__(ActiveLearningLoop)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                pool=RecordingDatabasePool(rows=[(1.0, 0)]),
                query="SELECT 1",
                target_column="y",
                feature_names=(),
            )


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_final_round_report(self) -> None:
        rows = [{"a": float(i), "y": i % 2} for i in range(40)]
        with Tapestry() as t:
            ActiveLearningLoop(
                pool=RecordingDatabasePool(rows=rows),
                query="SELECT a, y FROM data",
                target_column="y",
                feature_names=("a",),
                n_rounds=3,
                query_size=5,
                _config=KnotConfig(id="al"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        report: EvalReportPayload = result.outputs["al"]
        assert isinstance(report, EvalReportPayload)
        assert "accuracy" in report.metrics.scores
