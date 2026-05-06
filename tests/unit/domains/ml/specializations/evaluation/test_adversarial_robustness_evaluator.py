"""Tests for :class:`AdversarialRobustnessEvaluator`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.evaluation.adversarial_robustness_evaluator import (
    AdversarialRobustnessEvaluator,
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
    return TrainedModel(model_id="m1", algorithm="cnn", feature_names=("a",))


def _make_knot() -> AdversarialRobustnessEvaluator:
    with Tapestry():
        split = emit_split(_config=KnotConfig(id="split"))
        model = emit_model(_config=KnotConfig(id="model"))
        return AdversarialRobustnessEvaluator(
            model=model,
            split=split,
            _config=KnotConfig(id="adv"),
        )


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_invalid_attack(self) -> None:
        k = _make_knot()
        train = MLDataset(name="d:train", feature_names=("a",), row_count=80)
        test = MLDataset(name="d:test", feature_names=("a",), row_count=20)
        model = TrainedModel(model_id="m1", algorithm="cnn", feature_names=("a",))
        split = DataSplit(train=train, test=test)
        with self.assertRaises((TypeError, ValueError)):
            await k.process(model=model, split=split, attack="carlini", epsilon=0.1)

    async def test_rejects_nonpositive_epsilon(self) -> None:
        k = _make_knot()
        train = MLDataset(name="d:train", feature_names=("a",), row_count=80)
        test = MLDataset(name="d:test", feature_names=("a",), row_count=20)
        model = TrainedModel(model_id="m1", algorithm="cnn", feature_names=("a",))
        split = DataSplit(train=train, test=test)
        with self.assertRaises((TypeError, ValueError)):
            await k.process(model=model, split=split, attack="fgsm", epsilon=0.0)


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_robustness_report(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            model = emit_model(_config=KnotConfig(id="model"))
            AdversarialRobustnessEvaluator(
                model=model,
                split=split,
                attack="fgsm",
                epsilon=0.1,
                _config=KnotConfig(id="adv"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["adv"]
        assert 0.0 <= out["clean_accuracy"] <= 1.0
        assert 0.0 <= out["adversarial_accuracy"] <= 1.0
        assert out["attack"] == "fgsm"
        assert out["epsilon"] == 0.1
