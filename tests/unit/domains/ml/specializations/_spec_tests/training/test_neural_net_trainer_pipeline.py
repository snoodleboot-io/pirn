"""Tests for :class:`NeuralNetTrainerPipeline`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.specializations.training.neural_net_trainer_pipeline import (
    NeuralNetTrainerPipeline,
)
from pirn.domains.ml.types.dataset_manifest import DatasetManifest
from pirn.domains.ml.types.split_manifest import SplitManifest
from pirn.tapestry import Tapestry

from tests.unit.domains.ml._stubs.recording_lineage_store import RecordingLineageStore
from tests.unit.domains.ml._stubs.recording_object_store import RecordingObjectStore


def _split_fixture() -> SplitManifest:
    train = DatasetManifest(name="d:train", feature_names=("a",), target_name="y", row_count=80)
    test = DatasetManifest(name="d:test", feature_names=("a",), target_name="y", row_count=20)
    return SplitManifest(train=train, test=test)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_algorithm(self) -> None:
        with Tapestry():
            k = NeuralNetTrainerPipeline.__new__(NeuralNetTrainerPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                split=_split_fixture(),
                lineage=RecordingLineageStore(),
                store=RecordingObjectStore(),
                metrics=("accuracy",),
                algorithm="",
            )

    async def test_rejects_empty_metrics(self) -> None:
        with Tapestry():
            k = NeuralNetTrainerPipeline.__new__(NeuralNetTrainerPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                split=_split_fixture(),
                lineage=RecordingLineageStore(),
                store=RecordingObjectStore(),
                metrics=(),
                algorithm="pytorch",
            )

    async def test_rejects_invalid_format(self) -> None:
        with Tapestry():
            k = NeuralNetTrainerPipeline.__new__(NeuralNetTrainerPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                split=_split_fixture(),
                lineage=RecordingLineageStore(),
                store=RecordingObjectStore(),
                metrics=("accuracy",),
                algorithm="pytorch",
                format="tensorflow",
            )

    async def test_rejects_non_lineage_store(self) -> None:
        with Tapestry():
            k = NeuralNetTrainerPipeline.__new__(NeuralNetTrainerPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                split=_split_fixture(),
                lineage="not-a-store",  # type: ignore[arg-type]
                store=RecordingObjectStore(),
                metrics=("accuracy",),
            )
