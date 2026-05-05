"""Tests for :class:`NLGEvaluator`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.evaluation.nlg_evaluator import (
    NLGEvaluator,
)
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.ml_dataset import MLDataset
from pirn.domains.ml.types.trained_model import TrainedModel
from pirn.tapestry import Tapestry


@knot
async def emit_split() -> DataSplit:
    train = MLDataset(name="d:train", feature_names=("text",), row_count=80)
    test = MLDataset(name="d:test", feature_names=("text",), row_count=20)
    return DataSplit(train=train, test=test)


@knot
async def emit_model() -> TrainedModel:
    return TrainedModel(model_id="m1", algorithm="seq2seq", feature_names=("text",))


class TestConstruction(unittest.TestCase):
    def test_rejects_unknown_metric(self) -> None:
        with Tapestry():
            split = emit_split(_config=KnotConfig(id="split"))
            model = emit_model(_config=KnotConfig(id="model"))
            with self.assertRaisesRegex(ValueError, "metric"):
                NLGEvaluator(
                    model=model,
                    split=split,
                    metrics=("unknown_metric",),
                    _config=KnotConfig(id="bad"),
                )


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_nlg_metrics(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            model = emit_model(_config=KnotConfig(id="model"))
            NLGEvaluator(
                model=model,
                split=split,
                _config=KnotConfig(id="nlg"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["nlg"]
        assert "bleu" in out
        assert "rouge_l" in out
        assert "bert_score" in out
        for v in out.values():
            assert 0.0 <= v <= 1.0
