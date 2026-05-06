"""Tests for :class:`PerformanceTriggeredRetrainer`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.production.performance_triggered_retrainer import (
    PerformanceTriggeredRetrainer,
)
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.ml_dataset import MLDataset
from pirn.domains.ml.types.trained_model import TrainedModel
from pirn.tapestry import Tapestry


@knot
async def emit_split() -> DataSplit:
    train = MLDataset(name="d:train", feature_names=("a",), row_count=80)
    test = MLDataset(name="d:test", feature_names=("a",), row_count=20)
    return DataSplit(train=train, test=test)


@knot
async def emit_model() -> TrainedModel:
    return TrainedModel(model_id="m1", algorithm="logistic", feature_names=("a",))


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_metric(self) -> None:
        with Tapestry():
            k = PerformanceTriggeredRetrainer.__new__(PerformanceTriggeredRetrainer)
            object.__setattr__(k, "_config", KnotConfig(id="ptr"))
        split_val = DataSplit(
            train=MLDataset(name="t", feature_names=("a",), row_count=80),
            test=MLDataset(name="t2", feature_names=("a",), row_count=20),
        )
        model_val = TrainedModel(model_id="m1", algorithm="logistic", feature_names=("a",))
        with self.assertRaisesRegex((TypeError, ValueError), "metric"):
            await k.process(model=model_val, split=split_val, metric="", threshold=0.8)


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_evaluates_and_returns_triggered_flag(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            model = emit_model(_config=KnotConfig(id="model"))
            PerformanceTriggeredRetrainer(
                model=model,
                split=split,
                metric="accuracy",
                threshold=0.0,
                _config=KnotConfig(id="ptr"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["ptr"]
        assert "triggered" in out
        assert "current_score" in out
        assert out["metric"] == "accuracy"
