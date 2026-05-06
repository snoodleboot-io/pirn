"""Tests for :class:`TimeSeriesEvalPipeline`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.evaluation.timeseries_eval_pipeline import (
    TimeSeriesEvalPipeline,
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
    train = MLDataset(name="d:train", feature_names=("a",), row_count=80)
    test = MLDataset(name="d:test", feature_names=("a",), row_count=20)
    split = DataSplit(train=train, test=test)
    model = TrainedModel(
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
        report: EvalReport = result.outputs["ts-eval"]
        assert set(report.metrics.keys()) == {"mape", "smape", "mase"}
        assert report.details["time_column"] == "ts"
