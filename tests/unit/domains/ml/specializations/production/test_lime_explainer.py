"""Tests for :class:`LIMEExplainer`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.production.lime_explainer import (
    LIMEExplainer,
)
from pirn.domains.ml.types.split_manifest import SplitManifest
from pirn.domains.ml.types.dataset_manifest import DatasetManifest
from pirn.domains.ml.types.model_manifest import ModelManifest
from pirn.tapestry import Tapestry


@knot
async def emit_split() -> SplitManifest:
    train = DatasetManifest(name="d:train", feature_names=("a", "b"), row_count=80)
    test = DatasetManifest(name="d:test", feature_names=("a", "b"), row_count=20)
    return SplitManifest(train=train, test=test)


@knot
async def emit_model() -> ModelManifest:
    return ModelManifest(
        model_id="m1", algorithm="logistic", feature_names=("a", "b")
    )


def _make_split() -> SplitManifest:
    return SplitManifest(
        train=DatasetManifest(name="t", feature_names=("a", "b"), row_count=80),
        test=DatasetManifest(name="t2", feature_names=("a", "b"), row_count=20),
    )


def _make_model() -> ModelManifest:
    return ModelManifest(model_id="m1", algorithm="logistic", feature_names=("a", "b"))


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_zero_n_samples(self) -> None:
        with Tapestry():
            k = LIMEExplainer.__new__(LIMEExplainer)
            object.__setattr__(k, "_config", KnotConfig(id="lime"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(model=_make_model(), split=_make_split(), n_samples=0)


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_feature_importance(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            model = emit_model(_config=KnotConfig(id="model"))
            LIMEExplainer(
                model=model,
                split=split,
                n_samples=50,
                _config=KnotConfig(id="lime"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["lime"]
        assert set(out["feature_importance"].keys()) == {"a", "b"}
        assert out["n_samples"] == 50
        assert out["n_explained"] == 20
