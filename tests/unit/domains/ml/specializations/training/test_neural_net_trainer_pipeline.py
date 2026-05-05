"""Unit tests for :class:`NeuralNetTrainerPipeline`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.object_store import ObjectStore
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


class TestConstruction(unittest.TestCase):
    def test_rejects_invalid_format(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                NeuralNetTrainerPipeline(
                    split=_KnotStub(_config=KnotConfig(id="s")),
                    lineage=_StubLineage(),
                    store=_StubStore(),
                    metrics=["val_loss"],
                    format="keras",
                    _config=KnotConfig(id="nntp"),
                )

    def test_rejects_wrong_lineage_type(self) -> None:
        with self.assertRaises(TypeError):
            with Tapestry():
                NeuralNetTrainerPipeline(
                    split=_KnotStub(_config=KnotConfig(id="s")),
                    lineage="bad",  # type: ignore[arg-type]
                    store=_StubStore(),
                    metrics=["val_loss"],
                    _config=KnotConfig(id="nntp"),
                )

    def test_rejects_empty_metrics(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                NeuralNetTrainerPipeline(
                    split=_KnotStub(_config=KnotConfig(id="s")),
                    lineage=_StubLineage(),
                    store=_StubStore(),
                    metrics=[],
                    _config=KnotConfig(id="nntp"),
                )

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
