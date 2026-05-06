"""Tests for :class:`ActiveLearningLoop`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.specializations.task_pipelines.active_learning_loop import (
    ActiveLearningLoop,
)
from pirn.tapestry import Tapestry
from tests.unit.domains.ml._stubs.recording_database_pool import RecordingDatabasePool


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_pool(self) -> None:
        with Tapestry():
            k = ActiveLearningLoop.__new__(ActiveLearningLoop)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                pool="not-a-pool",  # type: ignore[arg-type]
                query="SELECT 1",
                target_column="y",
                feature_names=("a",),
            )

    async def test_rejects_empty_query(self) -> None:
        with Tapestry():
            k = ActiveLearningLoop.__new__(ActiveLearningLoop)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        pool = RecordingDatabasePool()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                pool=pool,
                query="",
                target_column="y",
                feature_names=("a",),
            )

    async def test_rejects_empty_feature_names(self) -> None:
        with Tapestry():
            k = ActiveLearningLoop.__new__(ActiveLearningLoop)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        pool = RecordingDatabasePool()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                pool=pool,
                query="SELECT 1",
                target_column="y",
                feature_names=(),
            )
