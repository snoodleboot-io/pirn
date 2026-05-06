"""Tests for :class:`BiasDetector`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.evaluation.bias_detector import (
    BiasDetector,
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
        algorithm="rf",
        feature_names=("a",),
        target_name="y",
    )


def _make_detector() -> BiasDetector:
    with Tapestry():
        split = emit_split(_config=KnotConfig(id="split"))
        model = emit_model(_config=KnotConfig(id="model"))
        detector = BiasDetector(
            model=model,
            split=split,
            sensitive_columns=("gender",),
            _config=KnotConfig(id="bd"),
        )
    return detector


def _fixtures():  # type: ignore[return]
    train = MLDataset(name="d:train", feature_names=("a",), row_count=80)
    test = MLDataset(name="d:test", feature_names=("a",), row_count=20)
    split = DataSplit(train=train, test=test)
    model = TrainedModel(
        model_id="m1", algorithm="rf", feature_names=("a",), target_name="y"
    )
    return model, split


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_sensitive_columns(self) -> None:
        detector = _make_detector()
        model, split = _fixtures()
        with self.assertRaises((TypeError, ValueError)):
            await detector.process(model=model, split=split, sensitive_columns=())


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_per_group_report(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            model = emit_model(_config=KnotConfig(id="model"))
            BiasDetector(
                model=model,
                split=split,
                sensitive_columns=("gender", "race"),
                _config=KnotConfig(id="bias"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        report: EvalReport = result.outputs["bias"]
        assert "parity_gender" in report.metrics
        assert "parity_race" in report.metrics
