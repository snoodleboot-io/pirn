"""Tests for :class:`RankingEvalPipeline`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.evaluation.ranking_eval_pipeline import (
    RankingEvalPipeline,
)
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.eval_report import EvalReport
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
        model_id="rank1",
        algorithm="lambdamart",
        feature_names=("a",),
        target_name="rel",
    )


def _make_pipeline() -> RankingEvalPipeline:
    with Tapestry():
        split = emit_split(_config=KnotConfig(id="split"))
        model = emit_model(_config=KnotConfig(id="model"))
        pipeline = RankingEvalPipeline(
            model=model,
            split=split,
            k=5,
            _config=KnotConfig(id="rank"),
        )
    return pipeline


def _fixtures():  # type: ignore[return]
    train = MLDataset(name="d:train", feature_names=("a",), row_count=80)
    test = MLDataset(name="d:test", feature_names=("a",), row_count=20)
    split = DataSplit(train=train, test=test)
    model = TrainedModel(
        model_id="rank1", algorithm="lambdamart", feature_names=("a",), target_name="rel"
    )
    return model, split


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_zero_k(self) -> None:
        pipeline = _make_pipeline()
        model, split = _fixtures()
        with self.assertRaises((TypeError, ValueError)):
            await pipeline.process(model=model, split=split, k=0)


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_ranking_report(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            model = emit_model(_config=KnotConfig(id="model"))
            RankingEvalPipeline(
                model=model,
                split=split,
                k=5,
                _config=KnotConfig(id="rank"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        report: EvalReport = result.outputs["rank"]
        assert "ndcg_at_5" in report.metrics
        assert "mrr" in report.metrics
        assert "map_at_5" in report.metrics
