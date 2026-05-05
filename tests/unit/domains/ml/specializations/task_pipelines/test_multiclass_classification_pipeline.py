"""Unit tests for :class:`MulticlassClassificationPipeline`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.ml.specializations.task_pipelines.multiclass_classification_pipeline import (
    MulticlassClassificationPipeline,
)
from pirn.tapestry import Tapestry


class _StubPool(DatabaseConnectionPool):
    pass


class TestConstruction(unittest.TestCase):
    def test_rejects_n_classes_less_than_3(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                MulticlassClassificationPipeline(
                    pool=_StubPool(),
                    query="SELECT 1",
                    target_column="label",
                    feature_names=["a"],
                    n_classes=2,
                    _config=KnotConfig(id="mcp"),
                )

    def test_rejects_empty_feature_names(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                MulticlassClassificationPipeline(
                    pool=_StubPool(),
                    query="SELECT 1",
                    target_column="label",
                    feature_names=[],
                    n_classes=3,
                    _config=KnotConfig(id="mcp"),
                )

    def test_valid_construction(self) -> None:
        with Tapestry() as t:
            MulticlassClassificationPipeline(
                pool=_StubPool(),
                query="SELECT * FROM data",
                target_column="label",
                feature_names=["a", "b"],
                n_classes=5,
                _config=KnotConfig(id="mcp"),
            )
        self.assertIsNotNone(t._store.get("mcp"))
