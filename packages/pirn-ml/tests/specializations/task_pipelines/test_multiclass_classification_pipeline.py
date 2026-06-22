"""Unit tests for :class:`MulticlassClassificationPipeline`."""

from __future__ import annotations

import unittest

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.core.knot_config import KnotConfig
from pirn_ml.specializations.task_pipelines.multiclass_classification_pipeline import (
    MulticlassClassificationPipeline,
)


class _StubPool(DatabaseConnectionPool):
    pass


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_n_classes_less_than_3(self) -> None:
        knot = MulticlassClassificationPipeline(
            pool=_StubPool(),
            query="SELECT 1",
            target_column="label",
            feature_names=["a"],
            n_classes=2,
            _config=KnotConfig(id="mcp"),
        )
        with self.assertRaises(ValueError):
            await knot.process(
                pool=_StubPool(),
                query="SELECT 1",
                target_column="label",
                feature_names=["a"],
                n_classes=2,
            )

    async def test_rejects_empty_feature_names(self) -> None:
        knot = MulticlassClassificationPipeline(
            pool=_StubPool(),
            query="SELECT 1",
            target_column="label",
            feature_names=[],
            n_classes=3,
            _config=KnotConfig(id="mcp"),
        )
        with self.assertRaises(ValueError):
            await knot.process(
                pool=_StubPool(),
                query="SELECT 1",
                target_column="label",
                feature_names=[],
                n_classes=3,
            )
