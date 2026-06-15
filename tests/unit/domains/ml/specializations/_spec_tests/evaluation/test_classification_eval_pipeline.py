"""Tests for :class:`ClassificationEvalPipeline`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_ml.specializations.evaluation.classification_eval_pipeline import (
    ClassificationEvalPipeline,
)
from pirn_ml.types.dataset_manifest import DatasetManifest
from pirn_ml.types.eval_report_payload import EvalReportPayload
from pirn_ml.types.model_manifest import ModelManifest
from pirn_ml.types.split_manifest import SplitManifest


@knot
async def emit_split() -> SplitManifest:
    train = DatasetManifest(name="d:train", feature_names=("a",), row_count=80)
    test = DatasetManifest(name="d:test", feature_names=("a",), row_count=20)
    return SplitManifest(train=train, test=test)


@knot
async def emit_model() -> ModelManifest:
    return ModelManifest(
        model_id="m1",
        algorithm="logistic",
        feature_names=("a",),
        target_name="y",
    )


def _make_pipeline() -> ClassificationEvalPipeline:
    with Tapestry():
        split = emit_split(_config=KnotConfig(id="split"))
        model = emit_model(_config=KnotConfig(id="model"))
        pipeline = ClassificationEvalPipeline(
            model=model,
            split=split,
            _config=KnotConfig(id="eval"),
        )
    return pipeline


def _fixtures():  # type: ignore[return]
    train = DatasetManifest(name="d:train", feature_names=("a",), row_count=80)
    test = DatasetManifest(name="d:test", feature_names=("a",), row_count=20)
    split = SplitManifest(train=train, test=test)
    model = ModelManifest(
        model_id="m1", algorithm="logistic", feature_names=("a",), target_name="y"
    )
    return model, split



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
        report: EvalReportPayload = result.outputs["eval-pipeline"]
        assert isinstance(report, EvalReportPayload)
        assert set(report.metrics.scores.keys()) == {
            "accuracy",
            "precision",
            "recall",
            "f1",
            "roc_auc",
            "confusion_matrix",
        }
        assert report.report.model_id == "m1"
