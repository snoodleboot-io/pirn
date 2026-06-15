"""Tests for :class:`ImageClassificationPipeline`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry
from pirn_ml.specializations.task_pipelines.image_classification_pipeline import (
    ImageClassificationPipeline,
)

from tests.unit.domains.ml._stubs.recording_database_pool import RecordingDatabasePool


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_pool(self) -> None:
        with Tapestry():
            k = ImageClassificationPipeline.__new__(ImageClassificationPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                pool="not-a-pool",  # type: ignore[arg-type]
                query="SELECT 1",
                image_column="img",
                label_column="label",
            )

    async def test_rejects_invalid_architecture(self) -> None:
        with Tapestry():
            k = ImageClassificationPipeline.__new__(ImageClassificationPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        pool = RecordingDatabasePool()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                pool=pool,
                query="SELECT 1",
                image_column="img",
                label_column="label",
                architecture="resnet",
            )

    async def test_rejects_empty_image_column(self) -> None:
        with Tapestry():
            k = ImageClassificationPipeline.__new__(ImageClassificationPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        pool = RecordingDatabasePool()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                pool=pool,
                query="SELECT 1",
                image_column="",
                label_column="label",
            )
