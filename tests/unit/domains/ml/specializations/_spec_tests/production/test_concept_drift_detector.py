"""Tests for :class:`ConceptDriftDetector`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_ml.specializations.production.concept_drift_detector import (
    ConceptDriftDetector,
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
    async def test_rejects_invalid_method(self) -> None:
        with Tapestry():
            k = ConceptDriftDetector.__new__(ConceptDriftDetector)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        model, split = _fixtures()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(model=model, split=split, method="unknown", delta=0.002)

    async def test_rejects_nonpositive_delta(self) -> None:
        with Tapestry():
            k = ConceptDriftDetector.__new__(ConceptDriftDetector)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        model, split = _fixtures()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(model=model, split=split, method="adwin", delta=0.0)


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_drift_detection_result(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            model = emit_model(_config=KnotConfig(id="model"))
            ConceptDriftDetector(
                model=model,
                split=split,
                method="adwin",
                delta=0.002,
                _config=KnotConfig(id="cdd"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["cdd"]
        assert "drift_detected" in out
        assert "statistic" in out
        assert out["method"] == "adwin"
