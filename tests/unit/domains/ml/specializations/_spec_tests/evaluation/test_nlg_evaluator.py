"""Tests for :class:`NLGEvaluator`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.evaluation.nlg_evaluator import NLGEvaluator
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
    return TrainedModel(
        model_id="m1",
        algorithm="seq2seq",
        feature_names=("text",),
        target_name="summary",
    )


def _fixtures():
    train = MLDataset(name="d:train", feature_names=("text",), row_count=80)
    test = MLDataset(name="d:test", feature_names=("text",), row_count=20)
    split = DataSplit(train=train, test=test)
    model = TrainedModel(
        model_id="m1", algorithm="seq2seq", feature_names=("text",), target_name="summary"
    )
    return model, split


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_unknown_metric(self) -> None:
        with Tapestry():
            k = NLGEvaluator.__new__(NLGEvaluator)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        model, split = _fixtures()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(model=model, split=split, metrics=("unknown_metric",))


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_bleu_and_rouge(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            model = emit_model(_config=KnotConfig(id="model"))
            NLGEvaluator(
                model=model,
                split=split,
                metrics=("bleu", "rouge_l"),
                _config=KnotConfig(id="nlg"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["nlg"]
        assert "bleu" in out
        assert "rouge_l" in out
