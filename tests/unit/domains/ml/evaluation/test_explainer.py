"""Tests for :class:`Explainer`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.evaluation.explainer import Explainer
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.ml_dataset import MLDataset
from pirn.domains.ml.types.trained_model import TrainedModel
from pirn.tapestry import Tapestry


@knot
async def emit_split() -> DataSplit:
    train = MLDataset(name="d:train", feature_names=("a", "b"), row_count=80)
    test = MLDataset(name="d:test", feature_names=("a", "b"), row_count=20)
    return DataSplit(train=train, test=test)


@knot
async def emit_model() -> TrainedModel:
    return TrainedModel(
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


class TestExplainerConstruction(unittest.TestCase):
    def test_rejects_unknown_method(self) -> None:
        with Tapestry():
            split = emit_split(_config=KnotConfig(id="split"))
            model = emit_model(_config=KnotConfig(id="model"))
            with self.assertRaisesRegex(ValueError, "method must be"):
                Explainer(
                    model=model,
                    split=split,
                    method="bogus",
                    _config=KnotConfig(id="bad"),
                )
