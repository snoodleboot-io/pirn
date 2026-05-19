"""Tests for :class:`TimeSeriesEvalPipeline`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.evaluation.timeseries_eval_pipeline import (
    TimeSeriesEvalPipeline,
)
from pirn.domains.ml.types.split_manifest import SplitManifest
from pirn.domains.ml.types.eval_metadata import EvalMetadata
from pirn.domains.ml.types.eval_report_payload import EvalReportPayload
from pirn.domains.ml.types.dataset_manifest import DatasetManifest
from pirn.domains.ml.types.model_manifest import ModelManifest
from pirn.tapestry import Tapestry


@knot
async def emit_split() -> SplitManifest:
    train = DatasetManifest(name="d:train", feature_names=("a",), row_count=80)
    test = DatasetManifest(name="d:test", feature_names=("a",), row_count=20)
    return SplitManifest(train=train, test=test)


@knot
async def emit_model() -> ModelManifest:
    return ModelManifest(
        model_id="ts1",
        algorithm="arima",
        feature_names=("a",),
        target_name="y",
    )


def _make_pipeline() -> TimeSeriesEvalPipeline:
    with Tapestry():
        split = emit_split(_config=KnotConfig(id="split"))
        model = emit_model(_config=KnotConfig(id="model"))
        pipeline = TimeSeriesEvalPipeline(
            model=model,
            split=split,
            time_column="ts",
            _config=KnotConfig(id="ts-eval"),
        )
    return pipeline


def _fixtures():  # type: ignore[return]
    train = DatasetManifest(name="d:train", feature_names=("a",), row_count=80)
    test = DatasetManifest(name="d:test", feature_names=("a",), row_count=20)
    split = SplitManifest(train=train, test=test)
    model = ModelManifest(
        model_id="ts1", algorithm="arima", feature_names=("a",), target_name="y"
    )
    return model, split


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_time_column(self) -> None:
        pipeline = _make_pipeline()
        model, split = _fixtures()
        with self.assertRaises((TypeError, ValueError)):
            await pipeline.process(model=model, split=split, time_column="")


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_records_time_column_in_details(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            model = emit_model(_config=KnotConfig(id="model"))
            TimeSeriesEvalPipeline(
                model=model,
                split=split,
                time_column="ts",
                _config=KnotConfig(id="ts-eval"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        report: EvalReportPayload = result.outputs["ts-eval"]
        assert set(report.metrics.scores.keys()) == {"mape", "smape", "mase"}
        assert report.metrics.details["time_column"] == "ts"
