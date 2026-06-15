"""Unit tests for :class:`BinaryClassificationPipeline`."""

from __future__ import annotations

import unittest

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.specializations.task_pipelines.binary_classification_pipeline import (
    BinaryClassificationPipeline,
)
from pirn.tapestry import Tapestry


class _StubPool(DatabaseConnectionPool):
    pass


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_query(self) -> None:
        with Tapestry():
            k = BinaryClassificationPipeline.__new__(BinaryClassificationPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                pool=_StubPool(),
                query="",
                target_column="label",
                feature_names=["a"],
            )

    async def test_rejects_empty_feature_names(self) -> None:
        with Tapestry():
            k = BinaryClassificationPipeline.__new__(BinaryClassificationPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                pool=_StubPool(),
                query="SELECT 1",
                target_column="label",
                feature_names=[],
            )

    async def test_rejects_non_pool(self) -> None:
        with Tapestry():
            k = BinaryClassificationPipeline.__new__(BinaryClassificationPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                pool="bad",  # type: ignore[arg-type]
                query="SELECT 1",
                target_column="label",
                feature_names=["a"],
            )
