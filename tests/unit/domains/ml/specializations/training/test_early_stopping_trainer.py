"""Unit tests for :class:`EarlyStoppingTrainer`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.specializations.training.early_stopping_trainer import (
    EarlyStoppingTrainer,
)
from pirn.tapestry import Tapestry


class _KnotStub(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> None:
        return None


class TestConstruction(unittest.TestCase):
    def test_rejects_patience_less_than_1(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                EarlyStoppingTrainer(
                    split=_KnotStub(_config=KnotConfig(id="s")),
                    algorithm="nn",
                    monitor_metric="val_loss",
                    patience=0,
                    _config=KnotConfig(id="est"),
                )

    def test_rejects_max_epochs_less_than_1(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                EarlyStoppingTrainer(
                    split=_KnotStub(_config=KnotConfig(id="s")),
                    algorithm="nn",
                    monitor_metric="val_loss",
                    max_epochs=0,
                    _config=KnotConfig(id="est"),
                )

    def test_rejects_empty_monitor_metric(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                EarlyStoppingTrainer(
                    split=_KnotStub(_config=KnotConfig(id="s")),
                    algorithm="nn",
                    monitor_metric="",
                    _config=KnotConfig(id="est"),
                )

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
