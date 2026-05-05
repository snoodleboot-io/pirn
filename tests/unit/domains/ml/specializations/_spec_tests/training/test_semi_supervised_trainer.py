"""Tests for :class:`SemiSupervisedTrainer`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.training.semi_supervised_trainer import (
    SemiSupervisedTrainer,
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


class TestConstruction(unittest.TestCase):
    def test_rejects_negative_unlabeled_row_count(self) -> None:
        with Tapestry():
            split = emit_split(_config=KnotConfig(id="split"))
            with self.assertRaisesRegex(ValueError, "unlabeled_row_count must be >= 0"):
                SemiSupervisedTrainer(
                    split=split,
                    algorithm="rf",
                    unlabeled_row_count=-1,
                    metrics=("accuracy",),
                    _config=KnotConfig(id="bad"),
                )

    def test_rejects_empty_algorithm(self) -> None:
        with Tapestry():
            split = emit_split(_config=KnotConfig(id="split"))
            with self.assertRaisesRegex(ValueError, "algorithm"):
                SemiSupervisedTrainer(
                    split=split,
                    algorithm="",
                    unlabeled_row_count=100,
                    metrics=("accuracy",),
                    _config=KnotConfig(id="bad"),
                )


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_returns_model_report_and_pseudo_labeled_rows(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            SemiSupervisedTrainer(
                split=split,
                algorithm="rf",
                unlabeled_row_count=200,
                metrics=("accuracy",),
                _config=KnotConfig(id="ss"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["ss"]
        assert isinstance(out, dict)
        assert isinstance(out["model"], TrainedModel)
        assert isinstance(out["eval_report"], EvalReport)
        assert out["pseudo_labeled_rows"] == 200
