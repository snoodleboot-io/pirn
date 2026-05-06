"""Unit tests for :class:`ComputerVisionPipeline`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.ml.image_encoder_provider import ImageEncoderProvider
from pirn.domains.ml.specializations.task_pipelines.computer_vision_pipeline import (
    ComputerVisionPipeline,
)
from pirn.tapestry import Tapestry


class _StubPool(DatabaseConnectionPool):
    pass


class _StubEncoder(ImageEncoderProvider):
    async def encode(self, images, *, model=None):
        return [[0.5] for _ in images]

    async def close(self) -> None:
        pass


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_image_column(self) -> None:
        with Tapestry():
            k = ComputerVisionPipeline.__new__(ComputerVisionPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                pool=_StubPool(),
                query="SELECT 1",
                image_column="",
                target_column="label",
                image_encoder=_StubEncoder(),
            )

    async def test_rejects_wrong_encoder_type(self) -> None:
        with Tapestry():
            k = ComputerVisionPipeline.__new__(ComputerVisionPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                pool=_StubPool(),
                query="SELECT 1",
                image_column="img",
                target_column="label",
                image_encoder="bad",  # type: ignore[arg-type]
            )
