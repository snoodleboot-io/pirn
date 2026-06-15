"""Tests for :class:`XGBoostTrainerPipeline`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.specializations.training.xgboost_trainer_pipeline import (
    XGBoostTrainerPipeline,
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
            k = XGBoostTrainerPipeline.__new__(XGBoostTrainerPipeline)
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
            k = XGBoostTrainerPipeline.__new__(XGBoostTrainerPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                split=_split_fixture(),
                lineage=RecordingLineageStore(),
                store=RecordingObjectStore(),
                metrics=(),
                algorithm="xgboost",
            )

    async def test_rejects_non_object_store(self) -> None:
        with Tapestry():
            k = XGBoostTrainerPipeline.__new__(XGBoostTrainerPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                split=_split_fixture(),
                lineage=RecordingLineageStore(),
                store="not-a-store",  # type: ignore[arg-type]
                metrics=("accuracy",),
                algorithm="xgboost",
            )
