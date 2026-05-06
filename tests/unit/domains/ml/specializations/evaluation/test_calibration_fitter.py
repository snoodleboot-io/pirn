"""Tests for :class:`CalibrationFitter`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.evaluation.calibration_fitter import (
    CalibrationFitter,
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


def _make_knot() -> CalibrationFitter:
    with Tapestry():
        split = emit_split(_config=KnotConfig(id="split"))
        model = emit_model(_config=KnotConfig(id="model"))
        return CalibrationFitter(
            model=model,
            split=split,
            _config=KnotConfig(id="cal"),
        )


class TestConstruction(unittest.TestCase):
    def test_rejects_non_knot_model(self) -> None:
        with Tapestry():
            split = emit_split(_config=KnotConfig(id="split"))
            with self.assertRaises(TypeError):
                CalibrationFitter(
                    model="bad",  # type: ignore[arg-type]
                    split=split,
                    _config=KnotConfig(id="bad"),
                )


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_invalid_method(self) -> None:
        k = _make_knot()
        train = MLDataset(name="d:train", feature_names=("a",), row_count=80)
        test = MLDataset(name="d:test", feature_names=("a",), row_count=20)
        model = TrainedModel(model_id="m1", algorithm="logistic", feature_names=("a",))
        split = DataSplit(train=train, test=test)
        with self.assertRaises((TypeError, ValueError)):
            await k.process(model=model, split=split, method="sigmoid")


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_returns_calibrated_trained_model(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            model = emit_model(_config=KnotConfig(id="model"))
            CalibrationFitter(
                model=model,
                split=split,
                method="platt",
                _config=KnotConfig(id="cal"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        calibrated: TrainedModel = result.outputs["cal"]
        assert isinstance(calibrated, TrainedModel)
        assert calibrated.algorithm == "calibrated_platt"
        assert calibrated.hyperparameters["base_model_id"] == "m1"
