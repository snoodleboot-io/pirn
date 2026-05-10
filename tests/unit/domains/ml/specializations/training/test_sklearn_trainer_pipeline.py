"""Unit tests for :class:`SklearnTrainerPipeline`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.object_store import ObjectStore
from pirn.domains.ml.lineage_store import LineageStore
from pirn.domains.ml.specializations.training.sklearn_trainer_pipeline import (
    SklearnTrainerPipeline,
)
from pirn.domains.ml.types.split_manifest import SplitManifest
from pirn.domains.ml.types.dataset_manifest import DatasetManifest
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


def _make_knot() -> SklearnTrainerPipeline:
    with Tapestry():
        k = SklearnTrainerPipeline.__new__(SklearnTrainerPipeline)
        object.__setattr__(k, "_config", KnotConfig(id="stp"))
    return k


def _split() -> SplitManifest:
    ds = DatasetManifest(name="ds", feature_names=("x",), target_name="y", row_count=10, source_uri="mem://")
    return SplitManifest(train=ds, test=ds)


class TestSklearnTrainerPipelineValidation(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_algorithm(self) -> None:
        k = _make_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                split=_split(),
                algorithm="",
                lineage=_StubLineage(),
                store=_StubStore(),
                metrics=["accuracy"],
            )

    async def test_rejects_wrong_lineage_type(self) -> None:
        k = _make_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                split=_split(),
                algorithm="rf",
                lineage="bad",  # type: ignore[arg-type]
                store=_StubStore(),
                metrics=["accuracy"],
            )

    async def test_rejects_empty_metrics(self) -> None:
        k = _make_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                split=_split(),
                algorithm="rf",
                lineage=_StubLineage(),
                store=_StubStore(),
                metrics=[],
            )


class TestSklearnTrainerPipelineConstruction(unittest.TestCase):
    def test_valid_construction(self) -> None:
        with Tapestry() as t:
            SklearnTrainerPipeline(
                split=_KnotStub(_config=KnotConfig(id="s")),
                algorithm="rf",
                lineage=_StubLineage(),
                store=_StubStore(),
                metrics=["accuracy"],
                _config=KnotConfig(id="stp"),
            )
        self.assertIsNotNone(t._store.get("stp"))
