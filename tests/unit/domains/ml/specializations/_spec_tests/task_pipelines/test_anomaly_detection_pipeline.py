"""Tests for :class:`AnomalyDetectionPipeline`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.specializations.task_pipelines.anomaly_detection_pipeline import (
    AnomalyDetectionPipeline,
)
from pirn.tapestry import Tapestry
from tests.unit.domains.ml._stubs.recording_database_pool import RecordingDatabasePool


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_pool(self) -> None:
        with Tapestry():
            k = AnomalyDetectionPipeline.__new__(AnomalyDetectionPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                pool="not-a-pool",  # type: ignore[arg-type]
                query="SELECT 1",
                feature_names=("a",),
            )

    async def test_rejects_invalid_algorithm(self) -> None:
        with Tapestry():
            k = AnomalyDetectionPipeline.__new__(AnomalyDetectionPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        pool = RecordingDatabasePool()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                pool=pool,
                query="SELECT 1",
                feature_names=("a",),
                algorithm="svm",
            )

    async def test_rejects_contamination_out_of_range(self) -> None:
        with Tapestry():
            k = AnomalyDetectionPipeline.__new__(AnomalyDetectionPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        pool = RecordingDatabasePool()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                pool=pool,
                query="SELECT 1",
                feature_names=("a",),
                algorithm="isolation_forest",
                contamination=0.6,
            )
