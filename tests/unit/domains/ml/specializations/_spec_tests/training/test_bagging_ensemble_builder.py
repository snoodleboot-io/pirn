"""Tests for :class:`BaggingEnsembleBuilder`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.training.bagging_ensemble_builder import (
    BaggingEnsembleBuilder,
)
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.eval_report import EvalReport
from pirn.domains.ml.types.ml_dataset import MLDataset
from pirn.domains.ml.types.trained_model import TrainedModel
from pirn.tapestry import Tapestry


@knot
async def emit_split() -> DataSplit:
    train = MLDataset(name="d:train", feature_names=("a", "b"), row_count=80)
    test = MLDataset(name="d:test", feature_names=("a", "b"), row_count=20)
    return DataSplit(train=train, test=test)


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_n_estimators_below_two(self) -> None:
        with Tapestry():
            k = BaggingEnsembleBuilder.__new__(BaggingEnsembleBuilder)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        split = DataSplit(
            train=MLDataset(name="d:train", feature_names=("a", "b"), row_count=80),
            test=MLDataset(name="d:test", feature_names=("a", "b"), row_count=20),
        )
        with self.assertRaises((TypeError, ValueError)):
            await k.process(split=split, algorithm="dt", n_estimators=1, metrics=("accuracy",))

    async def test_rejects_invalid_task(self) -> None:
        with Tapestry():
            k = BaggingEnsembleBuilder.__new__(BaggingEnsembleBuilder)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        split = DataSplit(
            train=MLDataset(name="d:train", feature_names=("a", "b"), row_count=80),
            test=MLDataset(name="d:test", feature_names=("a", "b"), row_count=20),
        )
        with self.assertRaises((TypeError, ValueError)):
            await k.process(split=split, algorithm="dt", task="clustering", metrics=("accuracy",))


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_returns_ensemble_model_and_eval_report(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            BaggingEnsembleBuilder(
                split=split,
                algorithm="dt",
                n_estimators=3,
                task="classification",
                metrics=("accuracy",),
                _config=KnotConfig(id="bag"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["bag"]
        assert isinstance(out, dict)
        assert isinstance(out["ensemble_model"], TrainedModel)
        assert isinstance(out["eval_report"], EvalReport)
        assert out["n_estimators"] == 3

    async def test_regression_task(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            BaggingEnsembleBuilder(
                split=split,
                algorithm="dt",
                n_estimators=2,
                task="regression",
                metrics=("mse",),
                _config=KnotConfig(id="bag"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        assert isinstance(result.outputs["bag"]["ensemble_model"], TrainedModel)
