"""Tests for :class:`FairnessAudit`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.evaluation.fairness_audit import FairnessAudit
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
        out: EvalReport = result.outputs["audit"]
        assert "parity_gender" in out.metrics
        assert "parity_race" in out.metrics


class TestFairnessAuditProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_sensitive_columns(self) -> None:
        auditor = FairnessAudit.__new__(FairnessAudit)
        object.__setattr__(auditor, "_config", KnotConfig(id="x"))
        train = MLDataset(name="d:train", feature_names=("a",), row_count=80)
        test = MLDataset(name="d:test", feature_names=("a",), row_count=20)
        split = DataSplit(train=train, test=test)
        model = TrainedModel(
            model_id="m1",
            algorithm="rf",
            feature_names=("a",),
            target_name="y",
        )
        with self.assertRaisesRegex(ValueError, "sensitive_columns"):
            await auditor.process(model=model, split=split, sensitive_columns=())
