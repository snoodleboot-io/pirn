"""Tests for :class:`PredictionDriftMonitor`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.production.prediction_drift_monitor import (
    PredictionDriftMonitor,
)
from pirn.domains.ml.types.split_manifest import SplitManifest
from pirn.domains.ml.types.dataset_manifest import DatasetManifest
from pirn.domains.ml.types.model_manifest import ModelManifest
from pirn.tapestry import Tapestry


@knot
async def emit_baseline() -> SplitManifest:
    train = DatasetManifest(name="b:train", feature_names=("a",), row_count=800)
    test = DatasetManifest(name="b:test", feature_names=("a",), row_count=200)
    return SplitManifest(train=train, test=test)


@knot
async def emit_current() -> SplitManifest:
    train = DatasetManifest(name="c:train", feature_names=("a",), row_count=100)
    test = DatasetManifest(name="c:test", feature_names=("a",), row_count=25)
    return SplitManifest(train=train, test=test)


@knot
async def emit_model() -> ModelManifest:
    return ModelManifest(model_id="m1", algorithm="logistic")


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_nonpositive_sigma(self) -> None:
        with Tapestry():
            k = PredictionDriftMonitor.__new__(PredictionDriftMonitor)
            object.__setattr__(k, "_config", KnotConfig(id="pdm"))
        baseline = SplitManifest(
            train=DatasetManifest(name="b:train", feature_names=("a",), row_count=800),
            test=DatasetManifest(name="b:test", feature_names=("a",), row_count=200),
        )
        current = SplitManifest(
            train=DatasetManifest(name="c:train", feature_names=("a",), row_count=100),
            test=DatasetManifest(name="c:test", feature_names=("a",), row_count=25),
        )
        model = ModelManifest(model_id="m1", algorithm="logistic")
        with self.assertRaisesRegex((TypeError, ValueError), "sigma_threshold"):
            await k.process(
                model=model, baseline=baseline, current=current, sigma_threshold=-1.0
            )


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
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
