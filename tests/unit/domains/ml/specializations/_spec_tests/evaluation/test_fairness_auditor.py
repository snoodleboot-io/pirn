"""Tests for :class:`FairnessAuditor`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.evaluation.fairness_auditor import (
    FairnessAuditor,
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
async def emit_model() -> TrainedModel:
    return TrainedModel(
        model_id="m1",
        algorithm="rf",
        feature_names=("a",),
        target_name="y",
    )


def _fixtures():
    train = MLDataset(name="d:train", feature_names=("a",), row_count=80)
    test = MLDataset(name="d:test", feature_names=("a",), row_count=20)
    split = DataSplit(train=train, test=test)
    model = TrainedModel(
        model_id="m1", algorithm="rf", feature_names=("a",), target_name="y"
    )
    return model, split


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_protected_attributes(self) -> None:
        with Tapestry():
            k = FairnessAuditor.__new__(FairnessAuditor)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        model, split = _fixtures()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(model=model, split=split, protected_attributes=())


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_fairness_metrics(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            model = emit_model(_config=KnotConfig(id="model"))
            FairnessAuditor(
                model=model,
                split=split,
                protected_attributes=("gender", "age"),
                _config=KnotConfig(id="fa"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["fa"]
        assert "demographic_parity" in out
        assert "equalized_odds" in out
        assert "individual_fairness" in out
