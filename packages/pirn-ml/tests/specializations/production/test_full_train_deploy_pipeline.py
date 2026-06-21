"""Unit tests for :class:`FullTrainDeployPipeline`."""

from __future__ import annotations

import unittest

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.connectors.object_store import ObjectStore
from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry
from pirn_ml.lineage_store import LineageStore
from pirn_ml.specializations.production.full_train_deploy_pipeline import (
    FullTrainDeployPipeline,
)


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


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_pool(self) -> None:
        with Tapestry():
            k = FullTrainDeployPipeline.__new__(FullTrainDeployPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="ftdp"))
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

    async def test_rejects_empty_feature_names(self) -> None:
        with Tapestry():
            k = FullTrainDeployPipeline.__new__(FullTrainDeployPipeline)
            object.__setattr__(k, "_config", KnotConfig(id="ftdp"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                pool=_StubPool(),
                query="SELECT * FROM t",
                name="m",
                feature_names=[],
                target_name="y",
                algorithm="rf",
                lineage=_StubLineage(),
                store=_StubStore(),
                metrics=["accuracy"],
            )

    def test_valid_construction(self) -> None:
        with Tapestry() as t:
            FullTrainDeployPipeline(
                pool=_StubPool(),
                query="SELECT * FROM data",
                name="model",
                feature_names=["a", "b"],
                target_name="y",
                algorithm="rf",
                lineage=_StubLineage(),
                store=_StubStore(),
                metrics=["accuracy"],
                _config=KnotConfig(id="ftdp"),
            )
        self.assertIsNotNone(t._store.get("ftdp"))
