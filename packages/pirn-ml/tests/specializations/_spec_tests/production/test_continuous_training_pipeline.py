"""Tests for :class:`ContinuousTrainingPipeline`."""

from __future__ import annotations

import unittest
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_ml.specializations.production.continuous_training_pipeline import (
    ContinuousTrainingPipeline,
)
from tests._stubs.recording_database_pool import (
    RecordingDatabasePool,
)
from tests._stubs.recording_lineage_store import (
    RecordingLineageStore,
)
from tests._stubs.recording_object_store import (
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


class _UnavailableLineageStore(RecordingLineageStore):
    """A lineage store whose registry is unreachable."""

    async def fetch_lineage(self, model_id: str) -> Mapping[str, Any]:
        self.fetches.append(model_id)
        raise ConnectionError("lineage registry unreachable")


class _FixedEventLineageStore(RecordingLineageStore):
    """A lineage store that returns one pre-canned last event."""

    def __init__(self, event: object) -> None:
        super().__init__()
        self._event = event

    async def fetch_lineage(self, model_id: str) -> Mapping[str, Any]:
        self.fetches.append(model_id)
        return {"model_id": model_id, "events": [self._event]}


class TestLineageFailuresDoNotRetrain(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def _wire(lineage: RecordingLineageStore, store: RecordingObjectStore) -> Tapestry:
        rows = [{"a": 1.0, "y": 0}, {"a": 2.0, "y": 1}] * 10
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
        return t

    async def test_lineage_outage_fails_the_run_without_deploying(self) -> None:
        lineage = _UnavailableLineageStore()
        store = RecordingObjectStore()
        result = await self._wire(lineage, store).run(RunRequest())
        assert not result.succeeded
        assert lineage.fetches == ["m"]
        assert lineage.events == []
        assert store.put_calls == []

    async def test_malformed_last_event_fails_the_run_without_deploying(self) -> None:
        lineage = _FixedEventLineageStore({"recorded_at": "not-a-date", "model_id": "m:1"})
        store = RecordingObjectStore()
        result = await self._wire(lineage, store).run(RunRequest())
        assert not result.succeeded
        assert lineage.events == []
        assert store.put_calls == []

    async def test_fresh_last_event_skips_retraining(self) -> None:
        recorded_at = datetime.now(UTC).isoformat()
        lineage = _FixedEventLineageStore({"recorded_at": recorded_at, "model_id": "m:cached"})
        store = RecordingObjectStore()
        result = await self._wire(lineage, store).run(RunRequest())
        assert result.succeeded
        assert result.outputs["cont"] == {
            "model_id": "m:cached",
            "eval_report": None,
            "skipped": True,
        }
        assert store.put_calls == []
