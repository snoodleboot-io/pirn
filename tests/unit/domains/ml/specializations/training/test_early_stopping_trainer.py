"""Unit tests for :class:`EarlyStoppingTrainer`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry
from pirn_ml.specializations.training.early_stopping_trainer import (
    EarlyStoppingTrainer,
)


class _KnotStub(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> None:
        return None


def _make_knot() -> EarlyStoppingTrainer:
    with Tapestry():
        k = EarlyStoppingTrainer.__new__(EarlyStoppingTrainer)
        object.__setattr__(k, "_config", KnotConfig(id="est"))
    return k


def _split():
    from pirn_ml.types.dataset_manifest import DatasetManifest
    from pirn_ml.types.split_manifest import SplitManifest

    return SplitManifest(
        train=DatasetManifest(name="tr", feature_names=["x"], target_name="y", row_count=10, source_uri="mem://"),
        test=DatasetManifest(name="te", feature_names=["x"], target_name="y", row_count=5, source_uri="mem://"),
    )


class TestEarlyStoppingTrainerValidation(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_patience_less_than_1(self) -> None:
        k = _make_knot()
        with self.assertRaises((ValueError, TypeError)):
            await k.process(split=_split(), algorithm="nn", monitor_metric="val_loss", patience=0)

    async def test_rejects_max_epochs_less_than_1(self) -> None:
        k = _make_knot()
        with self.assertRaises((ValueError, TypeError)):
            await k.process(split=_split(), algorithm="nn", monitor_metric="val_loss", max_epochs=0)

    async def test_rejects_empty_monitor_metric(self) -> None:
        k = _make_knot()
        with self.assertRaises((ValueError, TypeError)):
            await k.process(split=_split(), algorithm="nn", monitor_metric="")


class TestEarlyStoppingTrainerConstruction(unittest.TestCase):
    def test_valid_construction(self) -> None:
        with Tapestry() as t:
            EarlyStoppingTrainer(
                split=_KnotStub(_config=KnotConfig(id="s")),
                algorithm="nn",
                monitor_metric="val_loss",
                patience=10,
                max_epochs=100,
                _config=KnotConfig(id="est"),
            )
        self.assertIsNotNone(t._store.get("est"))
