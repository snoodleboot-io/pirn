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
    return TrainedModel(
        model_id="current", algorithm="rf", feature_names=("a",), target_name="y"
    )


@knot
async def emit_candidate() -> TrainedModel:
    return TrainedModel(
        model_id="candidate", algorithm="xgb", feature_names=("a",), target_name="y"
    )


def _fixtures():
    train = MLDataset(name="d:train", feature_names=("a",), row_count=80)
    test = MLDataset(name="d:test", feature_names=("a",), row_count=20)
    split = DataSplit(train=train, test=test)
    current = TrainedModel(
        model_id="current", algorithm="rf", feature_names=("a",), target_name="y"
    )
    candidate = TrainedModel(
        model_id="candidate", algorithm="xgb", feature_names=("a",), target_name="y"
    )
    return current, candidate, split


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_fraction_out_of_range(self) -> None:
        with Tapestry():
            k = CanaryDeployer.__new__(CanaryDeployer)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        current, candidate, split = _fixtures()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                current=current,
                candidate=candidate,
                split=split,
                canary_fraction=1.5,
                primary_metric="accuracy",
            )

    async def test_rejects_empty_primary_metric(self) -> None:
        with Tapestry():
            k = CanaryDeployer.__new__(CanaryDeployer)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        current, candidate, split = _fixtures()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                current=current,
                candidate=candidate,
                split=split,
                canary_fraction=0.1,
                primary_metric="",
            )


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_recommendation(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            current = emit_current(_config=KnotConfig(id="current"))
            candidate = emit_candidate(_config=KnotConfig(id="candidate"))
            CanaryDeployer(
                current=current,
                candidate=candidate,
                split=split,
                canary_fraction=0.1,
                primary_metric="accuracy",
                _config=KnotConfig(id="cd"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["cd"]
        assert out["recommendation"] in ("promote", "rollback")
        assert "current_score" in out
        assert "candidate_score" in out
