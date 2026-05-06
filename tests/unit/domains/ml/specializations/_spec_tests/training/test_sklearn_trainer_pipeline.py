"""Tests for :class:`SklearnTrainerPipeline`."""

from __future__ import annotations
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.specializations.training.sklearn_trainer_pipeline import (
    SklearnTrainerPipeline,
)
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.ml_dataset import MLDataset
from pirn.tapestry import Tapestry
from tests.unit.domains.ml._stubs.recording_lineage_store import RecordingLineageStore
from tests.unit.domains.ml._stubs.recording_object_store import RecordingObjectStore


def _split_fixture() -> DataSplit:
    train = MLDataset(name="d:train", feature_names=("a",), target_name="y", row_count=80)
    test = MLDataset(name="d:test", feature_names=("a",), target_name="y", row_count=20)
    return DataSplit(train=train, test=test)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_algorithm(self) -> None:
        with Tapestry():
            k = SklearnTrainerPipeline.__new__(SklearnTrainerPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                split=_split_fixture(),
                algorithm="",
                lineage=RecordingLineageStore(),
                store=RecordingObjectStore(),
                metrics=("accuracy",),
            )

    async def test_rejects_empty_metrics(self) -> None:
        with Tapestry():
            k = SklearnTrainerPipeline.__new__(SklearnTrainerPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                split=_split_fixture(),
                algorithm="rf",
                lineage=RecordingLineageStore(),
                store=RecordingObjectStore(),
                metrics=(),
            )

    async def test_rejects_non_lineage_store(self) -> None:
        with Tapestry():
            k = SklearnTrainerPipeline.__new__(SklearnTrainerPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                split=_split_fixture(),
                algorithm="rf",
                lineage="not-a-store",  # type: ignore[arg-type]
                store=RecordingObjectStore(),
                metrics=("accuracy",),
            )
