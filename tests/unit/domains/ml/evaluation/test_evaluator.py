"""Tests for :class:`Evaluator`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.evaluation.evaluator import Evaluator
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
        model_id="m1",
        algorithm="rf",
        feature_names=("a",),
        target_name="y",
    )


class TestEvaluatorHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_eval_report(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            model = emit_model(_config=KnotConfig(id="model"))
            Evaluator(
                model=model,
                split=split,
                metrics=("accuracy", "f1"),
                _config=KnotConfig(id="eval"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out: EvalReport = result.outputs["eval"]
        assert isinstance(out, EvalReport)
        assert out.model_id == "m1"
        assert set(out.metrics.keys()) == {"accuracy", "f1"}
        assert out.dataset_name == "d:test"


class TestEvaluatorProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_metrics(self) -> None:
        evaluator = Evaluator.__new__(Evaluator)
        object.__setattr__(evaluator, "_config", KnotConfig(id="x"))
        train = MLDataset(name="d:train", feature_names=("a",), row_count=80)
        test = MLDataset(name="d:test", feature_names=("a",), row_count=20)
        split = DataSplit(train=train, test=test)
        model = TrainedModel(
            model_id="m1",
            algorithm="rf",
            feature_names=("a",),
            target_name="y",
        )
        with self.assertRaisesRegex(ValueError, "metrics must be non-empty"):
            await evaluator.process(model=model, split=split, metrics=())
