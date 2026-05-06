"""Tests for :class:`ModelLineageTracker`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.production.model_lineage_tracker import (
    ModelLineageTracker,
)
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.eval_report import EvalReport
from pirn.domains.ml.types.ml_dataset import MLDataset
from pirn.domains.ml.types.trained_model import TrainedModel
from pirn.tapestry import Tapestry
from tests.unit.domains.ml._stubs.recording_lineage_store import (
    RecordingLineageStore,
)


@knot
async def emit_dataset() -> MLDataset:
    return MLDataset(
        name="ds", feature_names=("a",), target_name="y", row_count=100
    )


@knot
async def emit_split() -> DataSplit:
    train = MLDataset(name="ds:train", feature_names=("a",), row_count=80)
    test = MLDataset(name="ds:test", feature_names=("a",), row_count=20)
    return DataSplit(train=train, test=test)


@knot
async def emit_model() -> TrainedModel:
    return TrainedModel(
        model_id="m1", algorithm="rf", feature_names=("a",), target_name="y"
    )


@knot
async def emit_report() -> EvalReport:
    return EvalReport(
        model_id="m1",
        dataset_name="ds:test",
        metrics={"accuracy": 0.9},
    )


class TestConstruction(unittest.TestCase):
    def test_rejects_non_lineage_store(self) -> None:
        with Tapestry():
            dataset = emit_dataset(_config=KnotConfig(id="ds"))
            split = emit_split(_config=KnotConfig(id="split"))
            model = emit_model(_config=KnotConfig(id="model"))
            report = emit_report(_config=KnotConfig(id="report"))
            with self.assertRaisesRegex(TypeError, "lineage"):
                ModelLineageTracker(
                    dataset=dataset,
                    split=split,
                    model=model,
                    report=report,
                    lineage="not-a-store",  # type: ignore[arg-type]
                    _config=KnotConfig(id="bad"),
                )


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_emits_one_event_per_stage(self) -> None:
        lineage = RecordingLineageStore()
        with Tapestry() as t:
            dataset = emit_dataset(_config=KnotConfig(id="ds"))
            split = emit_split(_config=KnotConfig(id="split"))
            model = emit_model(_config=KnotConfig(id="model"))
            report = emit_report(_config=KnotConfig(id="report"))
            ModelLineageTracker(
                dataset=dataset,
                split=split,
                model=model,
                report=report,
                lineage=lineage,
                _config=KnotConfig(id="track"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        lineage_id = result.outputs["track"]
        assert isinstance(lineage_id, str)
        recorded = [event[0] for event in lineage.events]
        assert recorded == [
            "dataset_observed",
            "split_observed",
            "model_observed",
            "report_observed",
        ]
