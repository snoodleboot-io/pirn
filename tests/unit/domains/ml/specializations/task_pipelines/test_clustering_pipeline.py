"""Tests for :class:`ClusteringPipeline`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.task_pipelines.clustering_pipeline import (
    ClusteringPipeline,
)
from pirn.domains.ml.types.eval_report import EvalReport
from pirn.tapestry import Tapestry
from tests.unit.domains.ml._stubs.recording_database_pool import (
    RecordingDatabasePool,
)


class TestConstruction:
    def test_rejects_n_clusters_less_than_two(self) -> None:
        with Tapestry():
            with pytest.raises(ValueError, match="n_clusters"):
                ClusteringPipeline(
                    pool=RecordingDatabasePool(rows=[(1.0, 2.0)]),
                    query="SELECT 1",
                    feature_names=("a",),
                    n_clusters=1,
                    _config=KnotConfig(id="bad"),
                )

    def test_rejects_invalid_algorithm(self) -> None:
        with Tapestry():
            with pytest.raises(ValueError, match="algorithm"):
                ClusteringPipeline(
                    pool=RecordingDatabasePool(rows=[(1.0,)]),
                    query="SELECT 1",
                    feature_names=("a",),
                    algorithm="spectral",
                    _config=KnotConfig(id="bad"),
                )


@pytest.mark.asyncio
class TestHappyPath:
    async def test_emits_clustering_report(self) -> None:
        rows = [(float(i), float(i * 2)) for i in range(40)]
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
        report: EvalReport = result.outputs["cl"]
        assert isinstance(report, EvalReport)
        assert "silhouette" in report.metrics
