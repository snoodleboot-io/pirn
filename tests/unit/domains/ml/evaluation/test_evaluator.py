"""Tests for :class:`Evaluator`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.evaluation.evaluator import Evaluator
from pirn.domains.ml.types.dataset_manifest import DatasetManifest
from pirn.domains.ml.types.eval_metadata import EvalMetadata
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
        out: EvalReportPayload = result.outputs["eval"]
        assert isinstance(out, EvalReportPayload)
        assert isinstance(out.report, EvalMetadata)
        assert out.report.model_id == "m1"
        assert set(out.metrics.scores.keys()) == {"accuracy", "f1"}
        assert out.report.dataset_name == "d:test"


class TestEvaluatorProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_metrics(self) -> None:
        evaluator = Evaluator.__new__(Evaluator)
        object.__setattr__(evaluator, "_config", KnotConfig(id="x"))
        train = DatasetManifest(name="d:train", feature_names=("a",), row_count=80)
        test = DatasetManifest(name="d:test", feature_names=("a",), row_count=20)
        split = SplitManifest(train=train, test=test)
        model = ModelManifest(
            model_id="m1",
            algorithm="rf",
            feature_names=("a",),
            target_name="y",
        )
        with self.assertRaisesRegex(ValueError, "metrics must be non-empty"):
            await evaluator.process(model=model, split=split, metrics=())
