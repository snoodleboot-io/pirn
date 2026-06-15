"""Tests for :class:`CollaborativeFilteringPipeline`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.specializations.task_pipelines.collaborative_filtering_pipeline import (
    CollaborativeFilteringPipeline,
)
from pirn.tapestry import Tapestry

from tests.unit.domains.ml._stubs.recording_database_pool import RecordingDatabasePool


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_pool(self) -> None:
        with Tapestry():
            k = CollaborativeFilteringPipeline.__new__(CollaborativeFilteringPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                pool="not-a-pool",  # type: ignore[arg-type]
                query="SELECT 1",
                user_column="user",
                item_column="item",
                rating_column="rating",
            )

    async def test_rejects_invalid_algorithm(self) -> None:
        with Tapestry():
            k = CollaborativeFilteringPipeline.__new__(CollaborativeFilteringPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        pool = RecordingDatabasePool()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                pool=pool,
                query="SELECT 1",
                user_column="user",
                item_column="item",
                rating_column="rating",
                algorithm="nmf",
            )

    async def test_rejects_zero_top_k(self) -> None:
        with Tapestry():
            k = CollaborativeFilteringPipeline.__new__(CollaborativeFilteringPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        pool = RecordingDatabasePool()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                pool=pool,
                query="SELECT 1",
                user_column="user",
                item_column="item",
                rating_column="rating",
                algorithm="als",
                top_k=0,
            )
