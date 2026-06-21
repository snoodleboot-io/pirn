"""Tests for :class:`PredictionIntervalEstimator`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_ml.specializations.evaluation.prediction_interval_estimator import (
    PredictionIntervalEstimator,
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
    return ModelManifest(model_id="m1", algorithm="linear", feature_names=("a",))


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
        train = DatasetManifest(name="d:train", feature_names=("a",), row_count=80)
        test = DatasetManifest(name="d:test", feature_names=("a",), row_count=20)
        split = SplitManifest(train=train, test=test)
        model = ModelManifest(model_id="m1", algorithm="linear", feature_names=("a",))
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
