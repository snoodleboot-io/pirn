"""Tests for :class:`ConceptDriftDetector`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.production.concept_drift_detector import (
    ConceptDriftDetector,
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
    return ModelManifest(model_id="m1", algorithm="logistic")


def _make_split() -> SplitManifest:
    train = DatasetManifest(name="d:train", feature_names=("a",), row_count=80)
    test = DatasetManifest(name="d:test", feature_names=("a",), row_count=20)
    return SplitManifest(train=train, test=test)


def _make_model() -> ModelManifest:
    return ModelManifest(model_id="m1", algorithm="logistic")


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_invalid_method(self) -> None:
        with Tapestry():
            k = ConceptDriftDetector.__new__(ConceptDriftDetector)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                model=_make_model(),
                split=_make_split(),
                method="eddm",
                delta=0.002,
            )

    async def test_rejects_nonpositive_delta(self) -> None:
        with Tapestry():
            k = ConceptDriftDetector.__new__(ConceptDriftDetector)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                model=_make_model(),
                split=_make_split(),
                method="adwin",
                delta=0.0,
            )


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_concept_drift_result(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            model = emit_model(_config=KnotConfig(id="model"))
            ConceptDriftDetector(
                model=model,
                split=split,
                method="adwin",
                _config=KnotConfig(id="cd"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["cd"]
        assert isinstance(out["drift_detected"], bool)
        assert 0.0 <= out["statistic"] <= 1.0
        assert out["method"] == "adwin"
