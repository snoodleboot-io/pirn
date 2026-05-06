"""Tests for :class:`ABTestDeployer`."""

from __future__ import annotations
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.production.ab_test_deployer import (
    ABTestDeployer,
)
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.ml_dataset import MLDataset
from pirn.domains.ml.types.trained_model import TrainedModel
from pirn.tapestry import Tapestry


def _fixtures():
    train = MLDataset(name="d:train", feature_names=("a",), row_count=80)
    test = MLDataset(name="d:test", feature_names=("a",), row_count=20)
    split = DataSplit(train=train, test=test)
    model_a = TrainedModel(
        model_id="ma", algorithm="rf", feature_names=("a",), target_name="y"
    )
    model_b = TrainedModel(
        model_id="mb", algorithm="xgb", feature_names=("a",), target_name="y"
    )
    return model_a, model_b, split


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_primary_metric(self) -> None:
        with Tapestry():
            k = ABTestDeployer.__new__(ABTestDeployer)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        model_a, model_b, split = _fixtures()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                model_a=model_a,
                model_b=model_b,
                split=split,
                primary_metric="",
                alpha=0.05,
            )

    async def test_rejects_invalid_alpha(self) -> None:
        with Tapestry():
            k = ABTestDeployer.__new__(ABTestDeployer)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        model_a, model_b, split = _fixtures()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                model_a=model_a,
                model_b=model_b,
                split=split,
                primary_metric="accuracy",
                alpha=1.5,
            )
