"""Tests for :class:`RegressionPipeline`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.task_pipelines.regression_pipeline import (
    RegressionPipeline,
)
from pirn.domains.ml.types.eval_metadata import EvalMetadata
from pirn.domains.ml.types.eval_report_payload import EvalReportPayload
from pirn.tapestry import Tapestry
from tests.unit.domains.ml._stubs.recording_database_pool import (
    RecordingDatabasePool,
)


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_query(self) -> None:
        with Tapestry():
            k = RegressionPipeline.__new__(RegressionPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                pool=RecordingDatabasePool(rows=[(1, 0.5)]),
                query="",
                target_column="y",
                feature_names=("a",),
            )


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_regression_report(self) -> None:
        rows = [(float(i), float(i) * 0.5) for i in range(40)]
        with Tapestry() as t:
            RegressionPipeline(
                pool=RecordingDatabasePool(rows=rows),
                query="SELECT a, y FROM data",
                target_column="y",
                feature_names=("a",),
                _config=KnotConfig(id="reg"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        report: EvalReportPayload = result.outputs["reg"]
        assert isinstance(report, EvalReportPayload)
        assert {"rmse", "mae", "r2", "mape"}.issubset(report.metrics.scores.keys())
