"""Unit tests for :class:`RegressionPipeline`."""

from __future__ import annotations

import unittest

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.specializations.task_pipelines.regression_pipeline import (
    RegressionPipeline,
)


class _StubPool(DatabaseConnectionPool):
    pass


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_feature_names(self) -> None:
        knot = RegressionPipeline(
            pool=_StubPool(),
            query="SELECT 1",
            target_column="price",
            feature_names=[],
            _config=KnotConfig(id="rp"),
        )
        with self.assertRaises(ValueError):
            await knot.process(
                pool=_StubPool(),
                query="SELECT 1",
                target_column="price",
                feature_names=[],
            )

    async def test_rejects_empty_target_column(self) -> None:
        knot = RegressionPipeline(
            pool=_StubPool(),
            query="SELECT 1",
            target_column="",
            feature_names=["a"],
            _config=KnotConfig(id="rp"),
        )
        with self.assertRaises(ValueError):
            await knot.process(
                pool=_StubPool(),
                query="SELECT 1",
                target_column="",
                feature_names=["a"],
            )
