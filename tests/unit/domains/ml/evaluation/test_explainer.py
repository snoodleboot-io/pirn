"""Tests for :class:`Explainer`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.evaluation.explainer import Explainer
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
        model_id="m1",
        algorithm="rf",
        feature_names=("a", "b"),
        target_name="y",
    )


class TestExplainerHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_per_feature_importance(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            model = emit_model(_config=KnotConfig(id="model"))
            Explainer(
                model=model,
                split=split,
                method="permutation",
                _config=KnotConfig(id="explain"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["explain"]
        assert set(out.keys()) == {"a", "b"}


class TestExplainerProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_unknown_method(self) -> None:
        explainer = Explainer.__new__(Explainer)
        object.__setattr__(explainer, "_config", KnotConfig(id="x"))
        train = DatasetManifest(name="d:train", feature_names=("a", "b"), row_count=80)
        test = DatasetManifest(name="d:test", feature_names=("a", "b"), row_count=20)
        split = SplitManifest(train=train, test=test)
        model = ModelManifest(
            model_id="m1",
            algorithm="rf",
            feature_names=("a", "b"),
            target_name="y",
        )
        with self.assertRaisesRegex(ValueError, "method must be"):
            await explainer.process(model=model, split=split, method="bogus")
