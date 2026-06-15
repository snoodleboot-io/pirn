"""Tests for :class:`PredictionDriftMonitor`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.production.prediction_drift_monitor import (
    PredictionDriftMonitor,
)
from pirn.domains.ml.types.dataset_manifest import DatasetManifest
from pirn.domains.ml.types.model_manifest import ModelManifest
from pirn.domains.ml.types.split_manifest import SplitManifest
from pirn.tapestry import Tapestry


@knot
async def emit_split() -> SplitManifest:
    train = DatasetManifest(name="d:train", feature_names=("a",), row_count=80)
    test = DatasetManifest(name="d:test", feature_names=("a",), row_count=20)
    return SplitManifest(train=train, test=test)


@knot
async def emit_model() -> ModelManifest:
    return ModelManifest(
        model_id="m1", algorithm="rf", feature_names=("a",), target_name="y"
    )


def _fixtures():
    train = DatasetManifest(name="d:train", feature_names=("a",), row_count=80)
    test = DatasetManifest(name="d:test", feature_names=("a",), row_count=20)
    split = SplitManifest(train=train, test=test)
    model = ModelManifest(
        model_id="m1", algorithm="rf", feature_names=("a",), target_name="y"
    )
    return model, split


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_nonpositive_sigma_threshold(self) -> None:
        with Tapestry():
            k = PredictionDriftMonitor.__new__(PredictionDriftMonitor)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        model, split = _fixtures()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                model=model,
                baseline=split,
                current=split,
                sigma_threshold=0.0,
            )


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_z_score_and_alert(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            model = emit_model(_config=KnotConfig(id="model"))
            PredictionDriftMonitor(
                model=model,
                baseline=split,
                current=split,
                sigma_threshold=3.0,
                _config=KnotConfig(id="pdm"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["pdm"]
        assert "z_score" in out
        assert "alert" in out
        assert "baseline_mean" in out
