"""Tests for :class:`LRSchedulerTrainer`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.training.lr_scheduler_trainer import (
    LRSchedulerTrainer,
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


class TestConstruction:
    def test_rejects_invalid_scheduler(self) -> None:
        with Tapestry():
            split = emit_split(_config=KnotConfig(id="split"))
            with pytest.raises(ValueError, match="scheduler"):
                LRSchedulerTrainer(
                    split=split,
                    algorithm="nn",
                    scheduler="exponential",
                    metrics=("loss",),
                    _config=KnotConfig(id="bad"),
                )

    def test_rejects_empty_metrics(self) -> None:
        with Tapestry():
            split = emit_split(_config=KnotConfig(id="split"))
            with pytest.raises(ValueError, match="metrics must be non-empty"):
                LRSchedulerTrainer(
                    split=split,
                    algorithm="nn",
                    metrics=(),
                    _config=KnotConfig(id="bad"),
                )


class TestHappyPath:
    async def test_returns_model_report_and_scheduler(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            LRSchedulerTrainer(
                split=split,
                algorithm="nn",
                scheduler="cosine",
                metrics=("loss",),
                _config=KnotConfig(id="lrs"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["lrs"]
        assert isinstance(out, dict)
        assert isinstance(out["model"], TrainedModel)
        assert isinstance(out["eval_report"], EvalReport)
        assert out["scheduler"] == "cosine"

    async def test_step_scheduler(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            LRSchedulerTrainer(
                split=split,
                algorithm="nn",
                scheduler="step",
                metrics=("accuracy",),
                _config=KnotConfig(id="lrs"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        assert result.outputs["lrs"]["scheduler"] == "step"
