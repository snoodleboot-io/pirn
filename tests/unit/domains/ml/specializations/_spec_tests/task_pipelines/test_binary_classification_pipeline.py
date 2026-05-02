"""Tests for :class:`BinaryClassificationPipeline`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.task_pipelines.binary_classification_pipeline import (
    BinaryClassificationPipeline,
)
from pirn.domains.ml.types.eval_report import EvalReport
from pirn.tapestry import Tapestry
from tests.unit.domains.ml._stubs.recording_database_pool import (
    RecordingDatabasePool,
)


class TestConstruction:
    def test_rejects_empty_target_column(self) -> None:
        with Tapestry():
            with pytest.raises(ValueError, match="target_column"):
                BinaryClassificationPipeline(
                    pool=RecordingDatabasePool(rows=[(1, 0)]),
                    query="SELECT 1",
                    target_column="",
                    feature_names=("a",),
                    _config=KnotConfig(id="bad"),
                )

    def test_rejects_empty_feature_names(self) -> None:
        with Tapestry():
            with pytest.raises(ValueError, match="feature_names"):
                BinaryClassificationPipeline(
                    pool=RecordingDatabasePool(rows=[(1, 0)]),
                    query="SELECT 1",
                    target_column="y",
                    feature_names=(),
                    _config=KnotConfig(id="bad"),
                )


@pytest.mark.asyncio
class TestHappyPath:
    async def test_emits_classification_report(self) -> None:
        rows = [(float(i), i % 2) for i in range(40)]
        with Tapestry() as t:
            BinaryClassificationPipeline(
                pool=RecordingDatabasePool(rows=rows),
                query="SELECT a, y FROM data",
                target_column="y",
                feature_names=("a",),
                algorithm="logistic",
                _config=KnotConfig(id="bin"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        report: EvalReport = result.outputs["bin"]
        assert isinstance(report, EvalReport)
        assert "accuracy" in report.metrics
        assert "f1" in report.metrics
        assert "roc_auc" in report.metrics
