"""Tests for :class:`BaselineEstablisher`."""

from __future__ import annotations

import pytest

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


class TestConstruction:
    def test_rejects_non_knot_split(self) -> None:
        with Tapestry():
            with pytest.raises(TypeError, match="split must be a Knot"):
                BaselineEstablisher(
                    split="not-a-knot",  # type: ignore[arg-type]
                    _config=KnotConfig(id="bad"),
                )

    def test_rejects_empty_algorithm(self) -> None:
        with Tapestry():
            split = emit_split(_config=KnotConfig(id="split"))
            with pytest.raises(ValueError, match="algorithm"):
                BaselineEstablisher(
                    split=split,
                    algorithm="",
                    _config=KnotConfig(id="bad"),
                )

    def test_rejects_empty_metrics(self) -> None:
        with Tapestry():
            split = emit_split(_config=KnotConfig(id="split"))
            with pytest.raises(ValueError, match="metrics"):
                BaselineEstablisher(
                    split=split,
                    metrics=(),
                    _config=KnotConfig(id="bad"),
                )


class TestHappyPath:
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
