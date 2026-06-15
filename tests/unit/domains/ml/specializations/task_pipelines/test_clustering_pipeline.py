"""Tests for :class:`ClusteringPipeline`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.task_pipelines.clustering_pipeline import (
    ClusteringPipeline,
)
from pirn.domains.ml.types.eval_report_payload import EvalReportPayload
from pirn.tapestry import Tapestry

from tests.unit.domains.ml._stubs.recording_database_pool import (
    RecordingDatabasePool,
)


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_n_clusters_less_than_two(self) -> None:
        with Tapestry():
            k = ClusteringPipeline.__new__(ClusteringPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                pool=RecordingDatabasePool(rows=[(1.0, 2.0)]),
                query="SELECT 1",
                feature_names=("a",),
                n_clusters=1,
            )

    async def test_rejects_invalid_algorithm(self) -> None:
        with Tapestry():
            k = ClusteringPipeline.__new__(ClusteringPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                pool=RecordingDatabasePool(rows=[(1.0,)]),
                query="SELECT 1",
                feature_names=("a",),
                algorithm="spectral",
            )


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_clustering_report(self) -> None:
        rows = [{"a": float(i), "b": float(i * 2)} for i in range(40)]
        with Tapestry() as t:
            ClusteringPipeline(
                pool=RecordingDatabasePool(rows=rows),
                query="SELECT a, b FROM data",
                feature_names=("a",),
                algorithm="kmeans",
                n_clusters=3,
                _config=KnotConfig(id="cl"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        report: EvalReportPayload = result.outputs["cl"]
        assert isinstance(report, EvalReportPayload)
        assert "silhouette" in report.metrics.scores
