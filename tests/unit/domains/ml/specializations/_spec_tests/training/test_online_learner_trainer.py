"""Tests for :class:`OnlineLearnerTrainer`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.training.online_learner_trainer import (
    OnlineLearnerTrainer,
)
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.eval_report import EvalReport
from pirn.domains.ml.types.ml_dataset import MLDataset
from pirn.domains.ml.types.trained_model import TrainedModel
from pirn.tapestry import Tapestry


@knot
async def emit_split() -> DataSplit:
    train = MLDataset(name="d:train", feature_names=("a",), row_count=100)
    test = MLDataset(name="d:test", feature_names=("a",), row_count=20)
    return DataSplit(train=train, test=test)


class TestConstruction:
    def test_rejects_n_batches_below_one(self) -> None:
        with Tapestry():
            split = emit_split(_config=KnotConfig(id="split"))
            with pytest.raises(ValueError, match="n_batches must be >= 1"):
                OnlineLearnerTrainer(
                    split=split,
                    algorithm="sgd",
                    monitor_metric="accuracy",
                    n_batches=0,
                    _config=KnotConfig(id="bad"),
                )

    def test_rejects_empty_monitor_metric(self) -> None:
        with Tapestry():
            split = emit_split(_config=KnotConfig(id="split"))
            with pytest.raises(ValueError, match="monitor_metric"):
                OnlineLearnerTrainer(
                    split=split,
                    algorithm="sgd",
                    monitor_metric="",
                    _config=KnotConfig(id="bad"),
                )


class TestHappyPath:
    async def test_returns_model_report_and_batch_count(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            OnlineLearnerTrainer(
                split=split,
                algorithm="sgd",
                monitor_metric="accuracy",
                n_batches=5,
                _config=KnotConfig(id="ol"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["ol"]
        assert isinstance(out, dict)
        assert isinstance(out["model"], TrainedModel)
        assert isinstance(out["eval_report"], EvalReport)
        assert out["n_batches"] == 5
