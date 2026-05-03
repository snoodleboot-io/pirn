"""Tests for :class:`TimeSeriesForecastingPipeline`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.task_pipelines.time_series_forecasting_pipeline import (
    TimeSeriesForecastingPipeline,
)
from pirn.domains.ml.types.eval_report import EvalReport
from pirn.tapestry import Tapestry
from tests.unit.domains.ml._stubs.recording_database_pool import (
    RecordingDatabasePool,
)


class TestConstruction:
    def test_rejects_zero_horizon(self) -> None:
        with Tapestry():
            with pytest.raises(ValueError, match="horizon"):
                TimeSeriesForecastingPipeline(
                    pool=RecordingDatabasePool(rows=[(1.0, 1.0)]),
                    query="SELECT 1",
                    time_column="ts",
                    target_column="y",
                    feature_names=("a",),
                    horizon=0,
                    _config=KnotConfig(id="bad"),
                )

    def test_rejects_empty_feature_names(self) -> None:
        with Tapestry():
            with pytest.raises(ValueError, match="feature_names"):
                TimeSeriesForecastingPipeline(
                    pool=RecordingDatabasePool(rows=[(1.0,)]),
                    query="SELECT 1",
                    time_column="ts",
                    target_column="y",
                    feature_names=(),
                    _config=KnotConfig(id="bad"),
                )


@pytest.mark.asyncio
class TestHappyPath:
    async def test_emits_eval_report(self) -> None:
        rows = [(i, float(i), float(i)) for i in range(40)]
        with Tapestry() as t:
            TimeSeriesForecastingPipeline(
                pool=RecordingDatabasePool(rows=rows),
                query="SELECT ts, a, y FROM data",
                time_column="ts",
                target_column="y",
                feature_names=("a",),
                horizon=3,
                _config=KnotConfig(id="tsfp"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        report: EvalReport = result.outputs["tsfp"]
        assert isinstance(report, EvalReport)
