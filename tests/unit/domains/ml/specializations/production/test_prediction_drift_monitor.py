"""Tests for :class:`PredictionDriftMonitor`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.production.prediction_drift_monitor import (
    PredictionDriftMonitor,
)
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.ml_dataset import MLDataset
from pirn.domains.ml.types.trained_model import TrainedModel
from pirn.tapestry import Tapestry


@knot
async def emit_baseline() -> DataSplit:
    train = MLDataset(name="b:train", feature_names=("a",), row_count=800)
    test = MLDataset(name="b:test", feature_names=("a",), row_count=200)
    return DataSplit(train=train, test=test)


@knot
async def emit_current() -> DataSplit:
    train = MLDataset(name="c:train", feature_names=("a",), row_count=100)
    test = MLDataset(name="c:test", feature_names=("a",), row_count=25)
    return DataSplit(train=train, test=test)


@knot
async def emit_model() -> TrainedModel:
    return TrainedModel(model_id="m1", algorithm="logistic")


class TestConstruction:
    def test_rejects_nonpositive_sigma(self) -> None:
        with Tapestry():
            baseline = emit_baseline(_config=KnotConfig(id="b"))
            current = emit_current(_config=KnotConfig(id="c"))
            model = emit_model(_config=KnotConfig(id="model"))
            with pytest.raises(ValueError, match="sigma_threshold"):
                PredictionDriftMonitor(
                    model=model,
                    baseline=baseline,
                    current=current,
                    sigma_threshold=-1.0,
                    _config=KnotConfig(id="bad"),
                )


@pytest.mark.asyncio
class TestHappyPath:
    async def test_emits_z_score_and_alert(self) -> None:
        with Tapestry() as t:
            baseline = emit_baseline(_config=KnotConfig(id="b"))
            current = emit_current(_config=KnotConfig(id="c"))
            model = emit_model(_config=KnotConfig(id="model"))
            PredictionDriftMonitor(
                model=model,
                baseline=baseline,
                current=current,
                sigma_threshold=3.0,
                _config=KnotConfig(id="pdm"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["pdm"]
        assert "z_score" in out
        assert isinstance(out["alert"], bool)
        assert out["sigma_threshold"] == 3.0
