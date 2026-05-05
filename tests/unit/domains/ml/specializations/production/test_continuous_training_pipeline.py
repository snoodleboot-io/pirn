"""Unit tests for :class:`ContinuousTrainingPipeline`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.connectors.object_store import ObjectStore
from pirn.domains.ml.lineage_store import LineageStore
from pirn.domains.ml.specializations.production.continuous_training_pipeline import (
    ContinuousTrainingPipeline,
)
from pirn.tapestry import Tapestry


class _StubPool(DatabaseConnectionPool):
    pass


class _StubStore(ObjectStore):
    pass


class _StubLineage(LineageStore):
    async def log_event(self, event_type, payload) -> None:
        pass

    async def fetch_lineage(self, model_id):
        return {}

    async def close(self) -> None:
        pass


class TestConstruction(unittest.TestCase):
    def test_rejects_non_pool(self) -> None:
        with self.assertRaises(TypeError):
            with Tapestry():
                ContinuousTrainingPipeline(
                    pool="bad",  # type: ignore[arg-type]
                    query="SELECT 1",
                    name="m",
                    feature_names=["a"],
                    target_name="y",
                    algorithm="rf",
                    lineage=_StubLineage(),
                    store=_StubStore(),
                    metrics=["accuracy"],
                    _config=KnotConfig(id="ctp"),
                )

    def test_rejects_empty_query(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                ContinuousTrainingPipeline(
                    pool=_StubPool(),
                    query="",
                    name="m",
                    feature_names=["a"],
                    target_name="y",
                    algorithm="rf",
                    lineage=_StubLineage(),
                    store=_StubStore(),
                    metrics=["accuracy"],
                    _config=KnotConfig(id="ctp"),
                )

    def test_valid_construction(self) -> None:
        with Tapestry() as t:
            ContinuousTrainingPipeline(
                pool=_StubPool(),
                query="SELECT * FROM data",
                name="model",
                feature_names=["a", "b"],
                target_name="y",
                algorithm="rf",
                lineage=_StubLineage(),
                store=_StubStore(),
                metrics=["accuracy"],
                _config=KnotConfig(id="ctp"),
            )
        self.assertIsNotNone(t._store.get("ctp"))
