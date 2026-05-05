"""Unit tests for :class:`BinaryClassificationPipeline`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.ml.specializations.task_pipelines.binary_classification_pipeline import (
    BinaryClassificationPipeline,
)
from pirn.tapestry import Tapestry


class _StubPool(DatabaseConnectionPool):
    pass


class TestConstruction(unittest.TestCase):
    def test_rejects_empty_query(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                BinaryClassificationPipeline(
                    pool=_StubPool(),
                    query="",
                    target_column="label",
                    feature_names=["a"],
                    _config=KnotConfig(id="bcp"),
                )

    def test_rejects_empty_feature_names(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                BinaryClassificationPipeline(
                    pool=_StubPool(),
                    query="SELECT 1",
                    target_column="label",
                    feature_names=[],
                    _config=KnotConfig(id="bcp"),
                )

    def test_rejects_non_pool(self) -> None:
        with self.assertRaises(TypeError):
            with Tapestry():
                BinaryClassificationPipeline(
                    pool="bad",  # type: ignore[arg-type]
                    query="SELECT 1",
                    target_column="label",
                    feature_names=["a"],
                    _config=KnotConfig(id="bcp"),
                )

    def test_valid_construction(self) -> None:
        with Tapestry() as t:
            BinaryClassificationPipeline(
                pool=_StubPool(),
                query="SELECT * FROM data",
                target_column="label",
                feature_names=["a", "b"],
                _config=KnotConfig(id="bcp"),
            )
        self.assertIsNotNone(t._store.get("bcp"))
