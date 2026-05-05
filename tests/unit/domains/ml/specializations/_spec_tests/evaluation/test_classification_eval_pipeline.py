"""Tests for :class:`ClassificationEvalPipeline`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.evaluation.classification_eval_pipeline import (
    ClassificationEvalPipeline,
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
        model_id="m1",
        algorithm="logistic",
        feature_names=("a",),
        target_name="y",
    )


class TestConstruction(unittest.TestCase):
    def test_rejects_non_knot_model(self) -> None:
        with Tapestry():
            split = emit_split(_config=KnotConfig(id="split"))
            with self.assertRaisesRegex(TypeError, "model must be a Knot"):
                ClassificationEvalPipeline(
                    model="not-a-knot",  # type: ignore[arg-type]
                    split=split,
                    _config=KnotConfig(id="bad"),
                )

    def test_rejects_non_knot_split(self) -> None:
        with Tapestry():
            model = emit_model(_config=KnotConfig(id="model"))
            with self.assertRaisesRegex(TypeError, "split must be a Knot"):
                ClassificationEvalPipeline(
                    model=model,
                    split="not-a-knot",  # type: ignore[arg-type]
                    _config=KnotConfig(id="bad"),
                )


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_classification_report(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            model = emit_model(_config=KnotConfig(id="model"))
            ClassificationEvalPipeline(
                model=model,
                split=split,
                _config=KnotConfig(id="eval-pipeline"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        report: EvalReport = result.outputs["eval-pipeline"]
        assert isinstance(report, EvalReport)
        assert set(report.metrics.keys()) == {
            "accuracy",
            "precision",
            "recall",
            "f1",
            "roc_auc",
            "confusion_matrix",
        }
        assert report.model_id == "m1"
