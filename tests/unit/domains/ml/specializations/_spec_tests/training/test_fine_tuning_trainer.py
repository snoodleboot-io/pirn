"""Tests for :class:`FineTuningTrainer`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.training.fine_tuning_trainer import (
    FineTuningTrainer,
)
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.eval_report import EvalReport
from pirn.domains.ml.types.ml_dataset import MLDataset
from pirn.domains.ml.types.trained_model import TrainedModel
from pirn.tapestry import Tapestry


@knot
async def emit_split() -> DataSplit:
    train = MLDataset(name="d:train", feature_names=("x",), row_count=80)
    test = MLDataset(name="d:test", feature_names=("x",), row_count=20)
    return DataSplit(train=train, test=test)


class TestConstruction(unittest.TestCase):
    def test_rejects_empty_pretrained_model_id(self) -> None:
        with Tapestry():
            split = emit_split(_config=KnotConfig(id="split"))
            with self.assertRaisesRegex(ValueError, "pretrained_model_id"):
                FineTuningTrainer(
                    split=split,
                    pretrained_model_id="",
                    algorithm="nn",
                    metrics=("accuracy",),
                    _config=KnotConfig(id="bad"),
                )

    def test_rejects_negative_frozen_layers(self) -> None:
        with Tapestry():
            split = emit_split(_config=KnotConfig(id="split"))
            with self.assertRaisesRegex(ValueError, "frozen_layers must be >= 0"):
                FineTuningTrainer(
                    split=split,
                    pretrained_model_id="bert-base",
                    algorithm="nn",
                    metrics=("accuracy",),
                    frozen_layers=-1,
                    _config=KnotConfig(id="bad"),
                )


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_returns_model_report_and_pretrain_info(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            FineTuningTrainer(
                split=split,
                pretrained_model_id="bert-base",
                algorithm="nn",
                metrics=("accuracy",),
                frozen_layers=6,
                _config=KnotConfig(id="ft"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["ft"]
        assert isinstance(out, dict)
        assert isinstance(out["model"], TrainedModel)
        assert isinstance(out["eval_report"], EvalReport)
        assert out["pretrained_model_id"] == "bert-base"
        assert out["frozen_layers"] == 6
