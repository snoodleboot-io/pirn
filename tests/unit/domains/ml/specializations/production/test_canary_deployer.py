"""Tests for :class:`CanaryDeployer`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.production.canary_deployer import (
    CanaryDeployer,
)
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.ml_dataset import MLDataset
from pirn.domains.ml.types.trained_model import TrainedModel
from pirn.tapestry import Tapestry


@knot
async def emit_split() -> DataSplit:
    train = MLDataset(name="d:train", feature_names=("a",), row_count=80)
    test = MLDataset(name="d:test", feature_names=("a",), row_count=20)
    return DataSplit(train=train, test=test)


@knot
async def emit_current() -> TrainedModel:
    return TrainedModel(model_id="current-v1", algorithm="logistic")


@knot
async def emit_candidate() -> TrainedModel:
    return TrainedModel(model_id="candidate-v2", algorithm="random_forest")


class TestConstruction(unittest.TestCase):
    def test_rejects_fraction_out_of_range(self) -> None:
        with Tapestry():
            split = emit_split(_config=KnotConfig(id="split"))
            current = emit_current(_config=KnotConfig(id="cur"))
            candidate = emit_candidate(_config=KnotConfig(id="cand"))
            with self.assertRaisesRegex(ValueError, "canary_fraction"):
                CanaryDeployer(
                    current=current,
                    candidate=candidate,
                    split=split,
                    canary_fraction=1.1,
                    _config=KnotConfig(id="bad"),
                )


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_returns_comparison_report(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            current = emit_current(_config=KnotConfig(id="cur"))
            candidate = emit_candidate(_config=KnotConfig(id="cand"))
            CanaryDeployer(
                current=current,
                candidate=candidate,
                split=split,
                canary_fraction=0.1,
                primary_metric="accuracy",
                _config=KnotConfig(id="canary"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["canary"]
        assert "current_score" in out
        assert "candidate_score" in out
        assert out["canary_fraction"] == 0.1
        assert out["recommendation"] in ("promote", "rollback")
