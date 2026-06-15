"""Tests for :class:`RankingEvalPipeline`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.evaluation.ranking_eval_pipeline import (
    RankingEvalPipeline,
)
from pirn.domains.ml.types.dataset_manifest import DatasetManifest
from pirn.domains.ml.types.eval_report_payload import EvalReportPayload
from pirn.domains.ml.types.model_manifest import ModelManifest
from pirn.domains.ml.types.split_manifest import SplitManifest
from pirn.tapestry import Tapestry


@knot
async def emit_split() -> SplitManifest:
    train = DatasetManifest(name="d:train", feature_names=("a",), row_count=80)
    test = DatasetManifest(name="d:test", feature_names=("a",), row_count=20)
    return SplitManifest(train=train, test=test)


@knot
async def emit_model() -> ModelManifest:
    return ModelManifest(
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
    train = DatasetManifest(name="d:train", feature_names=("a",), row_count=80)
    test = DatasetManifest(name="d:test", feature_names=("a",), row_count=20)
    split = SplitManifest(train=train, test=test)
    model = ModelManifest(
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
        report: EvalReportPayload = result.outputs["rank"]
        assert "ndcg_at_5" in report.metrics.scores
        assert "mrr" in report.metrics.scores
        assert "map_at_5" in report.metrics.scores
