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


class TestConstruction(unittest.TestCase):
    def test_rejects_invalid_scheduler(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                LRSchedulerTrainer(
                    split=_KnotStub(_config=KnotConfig(id="s")),
                    algorithm="nn",
                    scheduler="warmup",
                    metrics=["val_loss"],
                    _config=KnotConfig(id="lrs"),
                )

    def test_rejects_empty_algorithm(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                LRSchedulerTrainer(
                    split=_KnotStub(_config=KnotConfig(id="s")),
                    algorithm="",
                    metrics=["val_loss"],
                    _config=KnotConfig(id="lrs"),
                )

    def test_rejects_empty_metrics(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                LRSchedulerTrainer(
                    split=_KnotStub(_config=KnotConfig(id="s")),
                    algorithm="nn",
                    metrics=[],
                    _config=KnotConfig(id="lrs"),
                )

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
