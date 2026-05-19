"""Tests for :class:`SHAPExplainer`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.production.shap_explainer import (
    SHAPExplainer,
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
        model_id="m1", algorithm="xgboost", feature_names=("a", "b")
    )


class TestConstruction(unittest.TestCase):
    def test_rejects_non_knot_split(self) -> None:
        with self.assertRaises(TypeError):
            with Tapestry():
                model = emit_model(_config=KnotConfig(id="model"))
                SHAPExplainer(
                    model=model,
                    split="bad",  # type: ignore[arg-type]
                    _config=KnotConfig(id="bad"),
                )


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_feature_importance(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            model = emit_model(_config=KnotConfig(id="model"))
            SHAPExplainer(
                model=model,
                split=split,
                _config=KnotConfig(id="shap"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["shap"]
        assert set(out["feature_importance"].keys()) == {"a", "b"}
        assert set(out["mean_abs_shap"].keys()) == {"a", "b"}
        assert out["model_id"] == "m1"
