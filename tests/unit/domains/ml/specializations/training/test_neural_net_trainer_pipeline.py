"""Unit tests for :class:`NeuralNetTrainerPipeline`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.connectors.object_store import ObjectStore
from pirn.domains.ml.lineage_store import LineageStore
from pirn.domains.ml.specializations.training.neural_net_trainer_pipeline import (
    NeuralNetTrainerPipeline,
)
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


def _make_knot() -> NeuralNetTrainerPipeline:
    with Tapestry():
        k = NeuralNetTrainerPipeline.__new__(NeuralNetTrainerPipeline)
        object.__setattr__(k, "_config", KnotConfig(id="nntp"))
    return k


def _split():
    from pirn.domains.ml.types.split_manifest import SplitManifest
    from pirn.domains.ml.types.dataset_manifest import DatasetManifest

    return SplitManifest(
        train=DatasetManifest(name="tr", feature_names=["x"], target_name="y", row_count=10, source_uri="mem://"),
        test=DatasetManifest(name="te", feature_names=["x"], target_name="y", row_count=5, source_uri="mem://"),
    )


class TestNeuralNetTrainerPipelineValidation(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_invalid_format(self) -> None:
        k = _make_knot()
        with self.assertRaises((ValueError, TypeError)):
            await k.process(split=_split(), lineage=_StubLineage(), store=_StubStore(), metrics=["val_loss"], format="keras")

    async def test_rejects_wrong_lineage_type(self) -> None:
        k = _make_knot()
        with self.assertRaises((ValueError, TypeError)):
            await k.process(split=_split(), lineage="bad", store=_StubStore(), metrics=["val_loss"])  # type: ignore[arg-type]

    async def test_rejects_empty_metrics(self) -> None:
        k = _make_knot()
        with self.assertRaises((ValueError, TypeError)):
            await k.process(split=_split(), lineage=_StubLineage(), store=_StubStore(), metrics=[])


class TestNeuralNetTrainerPipelineConstruction(unittest.TestCase):
    def test_valid_construction(self) -> None:
        with Tapestry() as t:
            NeuralNetTrainerPipeline(
                split=_KnotStub(_config=KnotConfig(id="s")),
                lineage=_StubLineage(),
                store=_StubStore(),
                metrics=["val_loss"],
                _config=KnotConfig(id="nntp"),
            )
        self.assertIsNotNone(t._store.get("nntp"))
