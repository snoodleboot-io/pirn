"""Tests for :class:`ROCAUCAnalyzer`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.evaluation.roc_auc_analyzer import (
    ROCAUCAnalyzer,
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
    return TrainedModel(model_id="m1", algorithm="logistic", feature_names=("a",))


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_roc_curve_and_auc(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            model = emit_model(_config=KnotConfig(id="model"))
            ROCAUCAnalyzer(
                model=model,
                split=split,
                _config=KnotConfig(id="roc"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["roc"]
        assert "fpr" in out and "tpr" in out
        assert "auc" in out and "optimal_threshold" in out
        assert len(out["fpr"]) == len(out["tpr"])
        assert 0.0 <= out["auc"] <= 1.0
