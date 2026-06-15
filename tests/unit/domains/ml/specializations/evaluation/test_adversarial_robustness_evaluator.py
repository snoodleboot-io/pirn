"""Tests for :class:`AdversarialRobustnessEvaluator`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_ml.specializations.evaluation.adversarial_robustness_evaluator import (
    AdversarialRobustnessEvaluator,
)
from pirn_ml.types.dataset_manifest import DatasetManifest
from pirn_ml.types.model_manifest import ModelManifest
from pirn_ml.types.split_manifest import SplitManifest


@knot
async def emit_split() -> SplitManifest:
    train = DatasetManifest(name="d:train", feature_names=("a",), row_count=80)
    test = DatasetManifest(name="d:test", feature_names=("a",), row_count=20)
    return SplitManifest(train=train, test=test)


@knot
async def emit_model() -> ModelManifest:
    return ModelManifest(model_id="m1", algorithm="cnn", feature_names=("a",))


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
        train = DatasetManifest(name="d:train", feature_names=("a",), row_count=80)
        test = DatasetManifest(name="d:test", feature_names=("a",), row_count=20)
        model = ModelManifest(model_id="m1", algorithm="cnn", feature_names=("a",))
        split = SplitManifest(train=train, test=test)
        with self.assertRaises((TypeError, ValueError)):
            await k.process(model=model, split=split, attack="carlini", epsilon=0.1)

    async def test_rejects_nonpositive_epsilon(self) -> None:
        k = _make_knot()
        train = DatasetManifest(name="d:train", feature_names=("a",), row_count=80)
        test = DatasetManifest(name="d:test", feature_names=("a",), row_count=20)
        model = ModelManifest(model_id="m1", algorithm="cnn", feature_names=("a",))
        split = SplitManifest(train=train, test=test)
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
