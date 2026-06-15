"""Tests for :class:`WalkForwardValidator`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_ml.specializations.evaluation.walk_forward_validator import (
    WalkForwardValidator,
)
from pirn_ml.types.dataset_manifest import DatasetManifest
from pirn_ml.types.eval_report_payload import EvalReportPayload


@knot
async def emit_dataset() -> DatasetManifest:
    return DatasetManifest(
        name="ts-data",
        feature_names=("a",),
        target_name="y",
        row_count=100,
    )


def _make_validator() -> WalkForwardValidator:
    with Tapestry():
        dataset = emit_dataset(_config=KnotConfig(id="ds"))
        validator = WalkForwardValidator(
            dataset=dataset,
            time_column="ts",
            train_window=20,
            test_window=5,
            algorithm="arima",
            _config=KnotConfig(id="walk"),
        )
    return validator


def _dataset() -> DatasetManifest:
    return DatasetManifest(
        name="ts-data", feature_names=("a",), target_name="y", row_count=100
    )


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_zero_train_window(self) -> None:
        validator = _make_validator()
        dataset = _dataset()
        with self.assertRaises((TypeError, ValueError)):
            await validator.process(
                dataset=dataset,
                time_column="ts",
                train_window=0,
                test_window=10,
                algorithm="arima",
            )

    async def test_rejects_empty_algorithm(self) -> None:
        validator = _make_validator()
        dataset = _dataset()
        with self.assertRaises((TypeError, ValueError)):
            await validator.process(
                dataset=dataset,
                time_column="ts",
                train_window=20,
                test_window=5,
                algorithm="",
            )


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_one_report_per_step(self) -> None:
        with Tapestry() as t:
            dataset = emit_dataset(_config=KnotConfig(id="ds"))
            WalkForwardValidator(
                dataset=dataset,
                time_column="ts",
                train_window=20,
                test_window=5,
                n_steps=3,
                algorithm="arima",
                _config=KnotConfig(id="walk"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        reports = result.outputs["walk"]
        assert isinstance(reports, tuple)
        assert len(reports) == 3
        for report in reports:
            assert isinstance(report, EvalReportPayload)
            assert set(report.metrics.scores.keys()) == {"mape", "smape", "mase"}
