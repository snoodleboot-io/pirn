"""Tests for :class:`DimensionalityReductionPipeline`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.task_pipelines.dimensionality_reduction_pipeline import (
    DimensionalityReductionPipeline,
)
from pirn.domains.ml.types.eval_report_payload import EvalReportPayload
from pirn.tapestry import Tapestry

from tests.unit.domains.ml._stubs.recording_database_pool import (
    RecordingDatabasePool,
)


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_invalid_algorithm(self) -> None:
        with Tapestry():
            k = DimensionalityReductionPipeline.__new__(DimensionalityReductionPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                pool=RecordingDatabasePool(rows=[(1.0, 2.0)]),
                query="SELECT 1",
                feature_names=("a",),
                algorithm="autoencoder",
            )

    async def test_rejects_zero_n_components(self) -> None:
        with Tapestry():
            k = DimensionalityReductionPipeline.__new__(DimensionalityReductionPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                pool=RecordingDatabasePool(rows=[(1.0,)]),
                query="SELECT 1",
                feature_names=("a",),
                n_components=0,
            )


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_reduction_report(self) -> None:
        rows = [{"a": float(i), "b": float(i * 2), "c": float(i * 3)} for i in range(40)]
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
        report: EvalReportPayload = result.outputs["dr"]
        assert isinstance(report, EvalReportPayload)
        assert "explained_variance" in report.metrics.scores
