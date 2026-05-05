"""Tests for :class:`RegressionPipeline`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.task_pipelines.regression_pipeline import (
    RegressionPipeline,
)
from pirn.domains.ml.types.eval_report import EvalReport
from pirn.tapestry import Tapestry
from tests.unit.domains.ml._stubs.recording_database_pool import (
    RecordingDatabasePool,
)


class TestConstruction(unittest.TestCase):
    def test_rejects_empty_query(self) -> None:
        with Tapestry():
            with self.assertRaisesRegex(ValueError, "query"):
                RegressionPipeline(
                    pool=RecordingDatabasePool(rows=[(1, 0.5)]),
                    query="",
                    target_column="y",
                    feature_names=("a",),
                    _config=KnotConfig(id="bad"),
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
        report: EvalReport = result.outputs["reg"]
        assert isinstance(report, EvalReport)
        assert {"rmse", "mae", "r2", "mape"}.issubset(report.metrics.keys())
