"""Unit tests for :class:`RegressionPipeline`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.ml.specializations.task_pipelines.regression_pipeline import (
    RegressionPipeline,
)
from pirn.tapestry import Tapestry


class _StubPool(DatabaseConnectionPool):
    pass


class TestConstruction(unittest.TestCase):
    def test_rejects_empty_feature_names(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                RegressionPipeline(
                    pool=_StubPool(),
                    query="SELECT 1",
                    target_column="price",
                    feature_names=[],
                    _config=KnotConfig(id="rp"),
                )

    def test_rejects_empty_target_column(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                RegressionPipeline(
                    pool=_StubPool(),
                    query="SELECT 1",
                    target_column="",
                    feature_names=["a"],
                    _config=KnotConfig(id="rp"),
                )

    def test_valid_construction(self) -> None:
        with Tapestry() as t:
            RegressionPipeline(
                pool=_StubPool(),
                query="SELECT * FROM data",
                target_column="price",
                feature_names=["a", "b"],
                _config=KnotConfig(id="rp"),
            )
        self.assertIsNotNone(t._store.get("rp"))
