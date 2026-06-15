"""Tests for :class:`Trainer`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.training.trainer import Trainer
from pirn.domains.ml.types.dataset_manifest import DatasetManifest
from pirn.domains.ml.types.model_manifest import ModelManifest
from pirn.domains.ml.types.split_manifest import SplitManifest
from pirn.tapestry import Tapestry


@knot
async def emit_split() -> SplitManifest:
    train = DatasetManifest(name="d:train", feature_names=("a", "b"), target_name="y", row_count=80)
    test = DatasetManifest(name="d:test", feature_names=("a", "b"), target_name="y", row_count=20)
    return SplitManifest(train=train, test=test)


class TestTrainerHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_trained_model(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            Trainer(
                split=split,
                algorithm="random_forest",
                hyperparameters={"n_estimators": 100},
                _config=KnotConfig(id="train"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out: ModelManifest = result.outputs["train"]
        assert isinstance(out, ModelManifest)
        assert out.algorithm == "random_forest"
        assert out.feature_names == ("a", "b")
        assert out.target_name == "y"
        assert out.model_id.startswith("random_forest:")
        assert dict(out.hyperparameters) == {"n_estimators": 100}


class TestTrainerConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_algorithm(self) -> None:
        train = DatasetManifest(name="d:train", feature_names=("a", "b"), target_name="y", row_count=80)
        test = DatasetManifest(name="d:test", feature_names=("a", "b"), target_name="y", row_count=20)
        split = SplitManifest(train=train, test=test)
        with Tapestry():
            k = Trainer.__new__(Trainer)
            object.__setattr__(k, "_config", KnotConfig(id="bad"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(split=split, algorithm="")
