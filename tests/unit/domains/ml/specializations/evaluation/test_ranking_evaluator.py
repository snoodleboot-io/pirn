"""Tests for :class:`RankingEvaluator`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.evaluation.ranking_evaluator import (
    RankingEvaluator,
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
    return TrainedModel(model_id="m1", algorithm="als", feature_names=("a",))


def _make_knot() -> RankingEvaluator:
    with Tapestry():
        split = emit_split(_config=KnotConfig(id="split"))
        model = emit_model(_config=KnotConfig(id="model"))
        k = RankingEvaluator(
            model=model,
            split=split,
            k=5,
            _config=KnotConfig(id="rank"),
        )
    return k


def _fixtures() -> tuple[TrainedModel, DataSplit]:
    train = MLDataset(name="d:train", feature_names=("a",), row_count=80)
    test = MLDataset(name="d:test", feature_names=("a",), row_count=20)
    split = DataSplit(train=train, test=test)
    model = TrainedModel(model_id="m1", algorithm="als", feature_names=("a",))
    return model, split


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_k_zero(self) -> None:
        knot = _make_knot()
        model, split = _fixtures()
        with self.assertRaisesRegex(ValueError, "k"):
            await knot.process(model=model, split=split, k=0)


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_ranking_metrics(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            model = emit_model(_config=KnotConfig(id="model"))
            RankingEvaluator(
                model=model,
                split=split,
                k=5,
                _config=KnotConfig(id="rank"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["rank"]
        assert "ndcg_at_k" in out
        assert "map_at_k" in out
        assert "mrr" in out
        assert "precision_at_k" in out
        assert out["k"] == 5
