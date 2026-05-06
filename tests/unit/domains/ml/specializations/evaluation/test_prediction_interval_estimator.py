"""Tests for :class:`PredictionIntervalEstimator`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.evaluation.prediction_interval_estimator import (
    PredictionIntervalEstimator,
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
    return TrainedModel(model_id="m1", algorithm="linear", feature_names=("a",))


def _make_knot() -> PredictionIntervalEstimator:
    with Tapestry():
        split = emit_split(_config=KnotConfig(id="split"))
        model = emit_model(_config=KnotConfig(id="model"))
        k = PredictionIntervalEstimator(
            model=model,
            split=split,
            coverage=0.9,
            _config=KnotConfig(id="pie"),
        )
    return k


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_coverage_out_of_range(self) -> None:
        knot = _make_knot()
        train = MLDataset(name="d:train", feature_names=("a",), row_count=80)
        test = MLDataset(name="d:test", feature_names=("a",), row_count=20)
        split = DataSplit(train=train, test=test)
        model = TrainedModel(model_id="m1", algorithm="linear", feature_names=("a",))
        with self.assertRaisesRegex(ValueError, "coverage"):
            await knot.process(model=model, split=split, coverage=1.5)


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_interval_report(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            model = emit_model(_config=KnotConfig(id="model"))
            PredictionIntervalEstimator(
                model=model,
                split=split,
                coverage=0.9,
                _config=KnotConfig(id="pie"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["pie"]
        assert out["coverage"] == 0.9
        assert 0.0 <= out["empirical_coverage"] <= 1.0
        assert "mean_interval_width" in out
        assert "model_id" in out
