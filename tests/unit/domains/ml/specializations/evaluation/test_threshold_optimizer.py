"""Tests for :class:`ThresholdOptimizer`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_ml.specializations.evaluation.threshold_optimizer import (
    ThresholdOptimizer,
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
    return ModelManifest(model_id="m1", algorithm="logistic", feature_names=("a",))


def _make_knot() -> ThresholdOptimizer:
    with Tapestry():
        split = emit_split(_config=KnotConfig(id="split"))
        model = emit_model(_config=KnotConfig(id="model"))
        k = ThresholdOptimizer(
            model=model,
            split=split,
            metric="f1",
            _config=KnotConfig(id="opt"),
        )
    return k


def _fixtures() -> tuple[ModelManifest, SplitManifest]:
    train = DatasetManifest(name="d:train", feature_names=("a",), row_count=80)
    test = DatasetManifest(name="d:test", feature_names=("a",), row_count=20)
    split = SplitManifest(train=train, test=test)
    model = ModelManifest(model_id="m1", algorithm="logistic", feature_names=("a",))
    return model, split


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_invalid_metric(self) -> None:
        knot = _make_knot()
        model, split = _fixtures()
        with self.assertRaisesRegex(ValueError, "metric"):
            await knot.process(model=model, split=split, metric="invalid")


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
