"""Tests for :class:`ThresholdOptimizer`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.evaluation.threshold_optimizer import (
    ThresholdOptimizer,
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


class TestConstruction(unittest.TestCase):
    def test_rejects_invalid_metric(self) -> None:
        with Tapestry():
            split = emit_split(_config=KnotConfig(id="split"))
            model = emit_model(_config=KnotConfig(id="model"))
            with self.assertRaisesRegex(ValueError, "metric"):
                ThresholdOptimizer(
                    model=model,
                    split=split,
                    metric="invalid",
                    _config=KnotConfig(id="bad"),
                )


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_optimal_threshold(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            model = emit_model(_config=KnotConfig(id="model"))
            ThresholdOptimizer(
                model=model,
                split=split,
                metric="f1",
                _config=KnotConfig(id="opt"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["opt"]
        assert 0.01 <= out["optimal_threshold"] <= 0.99
        assert 0.0 <= out["best_score"] <= 1.0
        assert out["metric"] == "f1"
        assert len(out["scores"]) == 99
