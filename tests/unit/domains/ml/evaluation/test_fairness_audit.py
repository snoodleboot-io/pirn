"""Tests for :class:`FairnessAudit`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_ml.evaluation.fairness_audit import FairnessAudit
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
        algorithm="rf",
        feature_names=("a",),
        target_name="y",
    )


class TestFairnessAuditHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_per_column_metrics(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            model = emit_model(_config=KnotConfig(id="model"))
            FairnessAudit(
                model=model,
                split=split,
                sensitive_columns=("gender", "race"),
                _config=KnotConfig(id="audit"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out: EvalReportPayload = result.outputs["audit"]
        assert isinstance(out, EvalReportPayload)
        assert "parity_gender" in out.metrics.scores
        assert "parity_race" in out.metrics.scores


class TestFairnessAuditProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_sensitive_columns(self) -> None:
        auditor = FairnessAudit.__new__(FairnessAudit)
        object.__setattr__(auditor, "_config", KnotConfig(id="x"))
        train = DatasetManifest(name="d:train", feature_names=("a",), row_count=80)
        test = DatasetManifest(name="d:test", feature_names=("a",), row_count=20)
        split = SplitManifest(train=train, test=test)
        model = ModelManifest(
            model_id="m1",
            algorithm="rf",
            feature_names=("a",),
            target_name="y",
        )
        with self.assertRaisesRegex(ValueError, "sensitive_columns"):
            await auditor.process(model=model, split=split, sensitive_columns=())
