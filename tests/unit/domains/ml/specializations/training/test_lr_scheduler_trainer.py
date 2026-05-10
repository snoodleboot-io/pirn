"""Unit tests for :class:`LRSchedulerTrainer`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.specializations.training.lr_scheduler_trainer import (
    LRSchedulerTrainer,
)
from pirn.tapestry import Tapestry


class _KnotStub(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> None:
        return None


def _make_knot() -> LRSchedulerTrainer:
    with Tapestry():
        k = LRSchedulerTrainer.__new__(LRSchedulerTrainer)
        object.__setattr__(k, "_config", KnotConfig(id="lrs"))
    return k


def _split():
    from pirn.domains.ml.types.split_manifest import SplitManifest
    from pirn.domains.ml.types.dataset_manifest import DatasetManifest

    return SplitManifest(
        train=DatasetManifest(name="tr", feature_names=["x"], target_name="y", row_count=10, source_uri="mem://"),
        test=DatasetManifest(name="te", feature_names=["x"], target_name="y", row_count=5, source_uri="mem://"),
    )


class TestLRSchedulerTrainerValidation(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_invalid_scheduler(self) -> None:
        k = _make_knot()
        with self.assertRaises((ValueError, TypeError)):
            await k.process(split=_split(), algorithm="nn", scheduler="warmup", metrics=["val_loss"])

    async def test_rejects_empty_algorithm(self) -> None:
        k = _make_knot()
        with self.assertRaises((ValueError, TypeError)):
            await k.process(split=_split(), algorithm="", metrics=["val_loss"])

    async def test_rejects_empty_metrics(self) -> None:
        k = _make_knot()
        with self.assertRaises((ValueError, TypeError)):
            await k.process(split=_split(), algorithm="nn", metrics=[])


class TestLRSchedulerTrainerConstruction(unittest.TestCase):
    def test_valid_construction(self) -> None:
        with Tapestry() as t:
            LRSchedulerTrainer(
                split=_KnotStub(_config=KnotConfig(id="s")),
                algorithm="nn",
                scheduler="cosine",
                metrics=["val_loss"],
                _config=KnotConfig(id="lrs"),
            )
        self.assertIsNotNone(t._store.get("lrs"))
