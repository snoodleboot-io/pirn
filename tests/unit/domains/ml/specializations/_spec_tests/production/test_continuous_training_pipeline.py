"""Tests for :class:`ContinuousTrainingPipeline`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.production.continuous_training_pipeline import (
    ContinuousTrainingPipeline,
)
from pirn.tapestry import Tapestry
from tests.unit.domains.ml._stubs.recording_database_pool import (
    RecordingDatabasePool,
)
from tests.unit.domains.ml._stubs.recording_lineage_store import (
    RecordingLineageStore,
)
from tests.unit.domains.ml._stubs.recording_object_store import (
    RecordingObjectStore,
)


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_negative_freshness_window(self) -> None:
        with Tapestry():
            k = ContinuousTrainingPipeline.__new__(ContinuousTrainingPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                pool=RecordingDatabasePool(rows=[(1,)]),
                query="SELECT 1",
                name="m",
                feature_names=("a",),
                target_name="y",
                algorithm="logistic",
                lineage=RecordingLineageStore(),
                store=RecordingObjectStore(),
                metrics=("accuracy",),
                freshness_window_days=-1,
            )


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_runs_full_training_when_no_lineage(self) -> None:
        rows = [{"a": 1.0, "y": 0}, {"a": 2.0, "y": 1}] * 10
        lineage = RecordingLineageStore()
        store = RecordingObjectStore()
        with Tapestry() as t:
            ContinuousTrainingPipeline(
                pool=RecordingDatabasePool(rows=rows),
                query="SELECT a, y FROM data",
                name="m",
                feature_names=("a",),
                target_name="y",
                algorithm="logistic",
                lineage=lineage,
                store=store,
                metrics=("accuracy",),
                freshness_window_days=1,
                _config=KnotConfig(id="cont"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["cont"]
        assert out["skipped"] is False
        assert isinstance(out["model_id"], str)
