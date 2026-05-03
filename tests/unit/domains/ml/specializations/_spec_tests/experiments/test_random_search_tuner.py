"""Tests for :class:`RandomSearchTuner`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.experiments.random_search_tuner import (
    RandomSearchTuner,
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
    def test_rejects_n_trials_below_one(self) -> None:
        with Tapestry():
            split = emit_split(_config=KnotConfig(id="split"))
            with pytest.raises(ValueError, match="n_trials"):
                RandomSearchTuner(
                    split=split,
                    algorithm="rf",
                    search_space={"n": (1, 2)},
                    primary_metric="accuracy",
                    n_trials=0,
                    _config=KnotConfig(id="bad"),
                )

    def test_rejects_empty_primary_metric(self) -> None:
        with Tapestry():
            split = emit_split(_config=KnotConfig(id="split"))
            with pytest.raises(ValueError, match="primary_metric"):
                RandomSearchTuner(
                    split=split,
                    algorithm="rf",
                    search_space={"n": (1, 2)},
                    primary_metric="",
                    _config=KnotConfig(id="bad"),
                )

    def test_rejects_empty_search_space(self) -> None:
        with Tapestry():
            split = emit_split(_config=KnotConfig(id="split"))
            with pytest.raises(ValueError, match="search_space"):
                RandomSearchTuner(
                    split=split,
                    algorithm="rf",
                    search_space={},
                    primary_metric="accuracy",
                    _config=KnotConfig(id="bad"),
                )


class TestHappyPath:
    async def test_emits_best_model_and_eval_report(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            RandomSearchTuner(
                split=split,
                algorithm="rf",
                search_space={"n_estimators": (10, 20, 30)},
                primary_metric="accuracy",
                n_trials=3,
                _config=KnotConfig(id="rs"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["rs"]
        assert isinstance(out, dict)
        assert isinstance(out["best_model"], TrainedModel)
        assert isinstance(out["eval_report"], EvalReport)
        assert "accuracy" in out["eval_report"].metrics
