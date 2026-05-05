"""Tests for :class:`DimensionalityReductionPipeline`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.task_pipelines.dimensionality_reduction_pipeline import (
    DimensionalityReductionPipeline,
)
from pirn.domains.ml.types.eval_report import EvalReport
from pirn.tapestry import Tapestry
from tests.unit.domains.ml._stubs.recording_database_pool import (
    RecordingDatabasePool,
)


class TestConstruction(unittest.TestCase):
    def test_rejects_invalid_algorithm(self) -> None:
        with Tapestry():
            with self.assertRaisesRegex(ValueError, "algorithm"):
                DimensionalityReductionPipeline(
                    pool=RecordingDatabasePool(rows=[(1.0, 2.0)]),
                    query="SELECT 1",
                    feature_names=("a",),
                    algorithm="autoencoder",
                    _config=KnotConfig(id="bad"),
                )

    def test_rejects_zero_n_components(self) -> None:
        with Tapestry():
            with self.assertRaisesRegex(ValueError, "n_components"):
                DimensionalityReductionPipeline(
                    pool=RecordingDatabasePool(rows=[(1.0,)]),
                    query="SELECT 1",
                    feature_names=("a",),
                    n_components=0,
                    _config=KnotConfig(id="bad"),
                )


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_reduction_report(self) -> None:
        rows = [(float(i), float(i * 2), float(i * 3)) for i in range(40)]
        with Tapestry() as t:
            DimensionalityReductionPipeline(
                pool=RecordingDatabasePool(rows=rows),
                query="SELECT a, b, c FROM data",
                feature_names=("a", "b"),
                algorithm="pca",
                n_components=2,
                _config=KnotConfig(id="dr"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        report: EvalReport = result.outputs["dr"]
        assert isinstance(report, EvalReport)
        assert "explained_variance" in report.metrics
