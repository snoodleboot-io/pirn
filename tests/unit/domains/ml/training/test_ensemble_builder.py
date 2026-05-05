"""Tests for :class:`EnsembleBuilder`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.training.ensemble_builder import EnsembleBuilder
from pirn.domains.ml.types.trained_model import TrainedModel
from pirn.tapestry import Tapestry


@knot
async def emit_first_model() -> TrainedModel:
    return TrainedModel(
        model_id="m1",
        algorithm="rf",
        feature_names=("a", "b"),
        target_name="y",
    )


@knot
async def emit_second_model() -> TrainedModel:
    return TrainedModel(
        model_id="m2",
        algorithm="gbm",
        feature_names=("a", "b"),
        target_name="y",
    )


class TestEnsembleBuilderHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_meta_model(self) -> None:
        with Tapestry() as t:
            m1 = emit_first_model(_config=KnotConfig(id="m1"))
            m2 = emit_second_model(_config=KnotConfig(id="m2"))
            EnsembleBuilder(
                models=(m1, m2),
                strategy="stacking",
                _config=KnotConfig(id="ens"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out: TrainedModel = result.outputs["ens"]
        assert out.algorithm == "ensemble:stacking"
        assert out.feature_names == ("a", "b")
        child_ids = list(out.hyperparameters["child_model_ids"])
        assert child_ids == ["m1", "m2"]


class TestEnsembleBuilderConstruction(unittest.TestCase):
    def test_rejects_single_model(self) -> None:
        with Tapestry():
            m1 = emit_first_model(_config=KnotConfig(id="m1"))
            with self.assertRaisesRegex(ValueError, "at least two"):
                EnsembleBuilder(
                    models=(m1,),
                    _config=KnotConfig(id="bad"),
                )
