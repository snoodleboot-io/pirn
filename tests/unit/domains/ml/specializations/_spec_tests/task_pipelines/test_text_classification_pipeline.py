"""Tests for :class:`TextClassificationPipeline`."""

from __future__ import annotations
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.specializations.task_pipelines.text_classification_pipeline import (
    TextClassificationPipeline,
)
from pirn.tapestry import Tapestry
from tests.unit.domains.ml._stubs.recording_database_pool import RecordingDatabasePool


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_pool(self) -> None:
        with Tapestry():
            k = TextClassificationPipeline.__new__(TextClassificationPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                pool="not-a-pool",  # type: ignore[arg-type]
                query="SELECT 1",
                text_column="text",
                target_column="label",
            )

    async def test_rejects_invalid_vectorizer(self) -> None:
        with Tapestry():
            k = TextClassificationPipeline.__new__(TextClassificationPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        pool = RecordingDatabasePool()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                pool=pool,
                query="SELECT 1",
                text_column="text",
                target_column="label",
                vectorizer="bow",
            )

    async def test_rejects_empty_target_column(self) -> None:
        with Tapestry():
            k = TextClassificationPipeline.__new__(TextClassificationPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        pool = RecordingDatabasePool()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                pool=pool,
                query="SELECT 1",
                text_column="text",
                target_column="",
            )
