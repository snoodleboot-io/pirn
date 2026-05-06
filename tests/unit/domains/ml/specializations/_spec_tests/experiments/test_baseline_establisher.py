"""Tests for :class:`BaselineEstablisher`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.experiments.baseline_establisher import (
    BaselineEstablisher,
)
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.eval_report import EvalReport
from pirn.domains.ml.types.ml_dataset import MLDataset
from pirn.tapestry import Tapestry


@knot
async def emit_split() -> DataSplit:
    train = MLDataset(
        name="d:train", feature_names=("a", "b"), target_name="y", row_count=80
    )
    test = MLDataset(
        name="d:test", feature_names=("a", "b"), target_name="y", row_count=20
    )
    return DataSplit(train=train, test=test)


def _make_establisher() -> BaselineEstablisher:
    with Tapestry():
        split = emit_split(_config=KnotConfig(id="split"))
        establisher = BaselineEstablisher(
            split=split,
            algorithm="linear",
            metrics=("accuracy",),
            _config=KnotConfig(id="baseline"),
        )
    return establisher


def _split_fixture() -> DataSplit:
    train = MLDataset(
        name="d:train", feature_names=("a", "b"), target_name="y", row_count=80
    )
    test = MLDataset(
        name="d:test", feature_names=("a", "b"), target_name="y", row_count=20
    )
    return DataSplit(train=train, test=test)


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_algorithm(self) -> None:
        establisher = _make_establisher()
        split = _split_fixture()
        with self.assertRaises((TypeError, ValueError)):
            await establisher.process(split=split, algorithm="", metrics=("accuracy",))

    async def test_rejects_empty_metrics(self) -> None:
        establisher = _make_establisher()
        split = _split_fixture()
        with self.assertRaises((TypeError, ValueError)):
            await establisher.process(split=split, algorithm="linear", metrics=())


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_baseline_eval_report(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            BaselineEstablisher(
                split=split,
                algorithm="linear",
                metrics=("accuracy",),
                _config=KnotConfig(id="baseline"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        report = result.outputs["baseline"]
        assert isinstance(report, EvalReport)
        assert "accuracy" in report.metrics
        assert report.dataset_name == "d:test"
