"""Tests for :class:`NLGEvaluator`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.evaluation.nlg_evaluator import NLGEvaluator
from pirn.domains.ml.types.split_manifest import SplitManifest
from pirn.domains.ml.types.dataset_manifest import DatasetManifest
from pirn.domains.ml.types.model_manifest import ModelManifest
from pirn.tapestry import Tapestry


@knot
async def emit_split() -> SplitManifest:
    train = DatasetManifest(name="d:train", feature_names=("text",), row_count=80)
    test = DatasetManifest(name="d:test", feature_names=("text",), row_count=20)
    return SplitManifest(train=train, test=test)


@knot
async def emit_model() -> ModelManifest:
    return ModelManifest(
        model_id="m1",
        algorithm="seq2seq",
        feature_names=("text",),
        target_name="summary",
    )


def _fixtures():
    train = DatasetManifest(name="d:train", feature_names=("text",), row_count=80)
    test = DatasetManifest(name="d:test", feature_names=("text",), row_count=20)
    split = SplitManifest(train=train, test=test)
    model = ModelManifest(
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
