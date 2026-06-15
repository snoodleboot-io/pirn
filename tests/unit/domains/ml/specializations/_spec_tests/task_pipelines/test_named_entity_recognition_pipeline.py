"""Tests for :class:`NamedEntityRecognitionPipeline`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry
from pirn_ml.specializations.task_pipelines.named_entity_recognition_pipeline import (
    NamedEntityRecognitionPipeline,
)

from tests.unit.domains.ml._stubs.recording_database_pool import RecordingDatabasePool


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_pool(self) -> None:
        with Tapestry():
            k = NamedEntityRecognitionPipeline.__new__(NamedEntityRecognitionPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                pool="not-a-pool",  # type: ignore[arg-type]
                query="SELECT 1",
                text_column="text",
                label_column="label",
            )

    async def test_rejects_empty_text_column(self) -> None:
        with Tapestry():
            k = NamedEntityRecognitionPipeline.__new__(NamedEntityRecognitionPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        pool = RecordingDatabasePool()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                pool=pool,
                query="SELECT 1",
                text_column="",
                label_column="label",
            )

    async def test_rejects_empty_algorithm(self) -> None:
        with Tapestry():
            k = NamedEntityRecognitionPipeline.__new__(NamedEntityRecognitionPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        pool = RecordingDatabasePool()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                pool=pool,
                query="SELECT 1",
                text_column="text",
                label_column="label",
                algorithm="",
            )
