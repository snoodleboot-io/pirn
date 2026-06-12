"""Unit tests for :class:`ContinuousTrainingPipeline`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.connectors.object_store import ObjectStore
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


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_pool(self) -> None:
        with Tapestry():
            k = ContinuousTrainingPipeline.__new__(ContinuousTrainingPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                pool="bad",  # type: ignore[arg-type]
                query="SELECT 1",
                name="m",
                feature_names=["a"],
                target_name="y",
                algorithm="rf",
                lineage=_StubLineage(),
                store=_StubStore(),
                metrics=["accuracy"],
            )

    async def test_rejects_empty_query(self) -> None:
        with Tapestry():
            k = ContinuousTrainingPipeline.__new__(ContinuousTrainingPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                pool=_StubPool(),
                query="",
                name="m",
                feature_names=["a"],
                target_name="y",
                algorithm="rf",
                lineage=_StubLineage(),
                store=_StubStore(),
                metrics=["accuracy"],
            )

    async def test_rejects_empty_name(self) -> None:
        with Tapestry():
            k = ContinuousTrainingPipeline.__new__(ContinuousTrainingPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                pool=_StubPool(),
                query="SELECT 1",
                name="",
                feature_names=["a"],
                target_name="y",
                algorithm="rf",
                lineage=_StubLineage(),
                store=_StubStore(),
                metrics=["accuracy"],
            )
