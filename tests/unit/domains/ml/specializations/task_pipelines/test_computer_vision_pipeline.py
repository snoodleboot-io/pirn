"""Unit tests for :class:`ComputerVisionPipeline`."""

from __future__ import annotations

import unittest
from typing import Any

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


class TestConstruction(unittest.TestCase):
    def test_rejects_empty_image_column(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                ComputerVisionPipeline(
                    pool=_StubPool(),
                    query="SELECT 1",
                    image_column="",
                    target_column="label",
                    image_encoder=_StubEncoder(),
                    _config=KnotConfig(id="cvp"),
                )

    def test_rejects_wrong_encoder_type(self) -> None:
        with self.assertRaises(TypeError):
            with Tapestry():
                ComputerVisionPipeline(
                    pool=_StubPool(),
                    query="SELECT 1",
                    image_column="img",
                    target_column="label",
                    image_encoder="bad",  # type: ignore[arg-type]
                    _config=KnotConfig(id="cvp"),
                )

    def test_valid_construction(self) -> None:
        with Tapestry() as t:
            ComputerVisionPipeline(
                pool=_StubPool(),
                query="SELECT * FROM data",
                image_column="img",
                target_column="label",
                image_encoder=_StubEncoder(),
                _config=KnotConfig(id="cvp"),
            )
        self.assertIsNotNone(t._store.get("cvp"))
