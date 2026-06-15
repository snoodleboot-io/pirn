"""Unit tests for :class:`XGBoostTrainerPipeline`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.connectors.object_store import ObjectStore
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.lineage_store import LineageStore
from pirn.domains.ml.specializations.training.xgboost_trainer_pipeline import (
    XGBoostTrainerPipeline,
)
from pirn.domains.ml.types.dataset_manifest import DatasetManifest
from pirn.domains.ml.types.split_manifest import SplitManifest
from pirn.tapestry import Tapestry


class _StubStore(ObjectStore):
    pass


class _StubLineage(LineageStore):
    async def log_event(self, event_type, payload) -> None:
        pass

    async def fetch_lineage(self, model_id):
        return {}

    async def close(self) -> None:
        pass


class _KnotStub(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> None:
        return None


def _make_knot() -> XGBoostTrainerPipeline:
    with Tapestry():
        k = XGBoostTrainerPipeline.__new__(XGBoostTrainerPipeline)
        object.__setattr__(k, "_config", KnotConfig(id="xtp"))
    return k


def _split() -> SplitManifest:
    ds = DatasetManifest(name="ds", feature_names=("x",), target_name="y", row_count=10, source_uri="mem://")
    return SplitManifest(train=ds, test=ds)


class TestXGBoostTrainerPipelineValidation(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_wrong_store_type(self) -> None:
        k = _make_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                split=_split(),
                lineage=_StubLineage(),
                store="bad",  # type: ignore[arg-type]
                metrics=["accuracy"],
            )

    async def test_rejects_wrong_lineage_type(self) -> None:
        k = _make_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                split=_split(),
                lineage="bad",  # type: ignore[arg-type]
                store=_StubStore(),
                metrics=["accuracy"],
            )

    async def test_rejects_empty_metrics(self) -> None:
        k = _make_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                split=_split(),
                lineage=_StubLineage(),
                store=_StubStore(),
                metrics=[],
            )


class TestXGBoostTrainerPipelineConstruction(unittest.TestCase):
    def test_valid_construction(self) -> None:
        with Tapestry() as t:
            XGBoostTrainerPipeline(
                split=_KnotStub(_config=KnotConfig(id="s")),
                lineage=_StubLineage(),
                store=_StubStore(),
                metrics=["accuracy", "f1"],
                _config=KnotConfig(id="xtp"),
            )
        self.assertIsNotNone(t._store.get("xtp"))
