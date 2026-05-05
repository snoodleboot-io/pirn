"""Unit tests for :class:`OnlineLearnerTrainer`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.specializations.training.online_learner_trainer import (
    OnlineLearnerTrainer,
)
from pirn.tapestry import Tapestry


class _KnotStub(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> None:
        return None


class TestConstruction(unittest.TestCase):
    def test_rejects_n_batches_less_than_1(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                OnlineLearnerTrainer(
                    split=_KnotStub(_config=KnotConfig(id="s")),
                    algorithm="sgd",
                    monitor_metric="accuracy",
                    n_batches=0,
                    _config=KnotConfig(id="olt"),
                )

    def test_rejects_empty_monitor_metric(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                OnlineLearnerTrainer(
                    split=_KnotStub(_config=KnotConfig(id="s")),
                    algorithm="sgd",
                    monitor_metric="",
                    _config=KnotConfig(id="olt"),
                )

    def test_rejects_empty_algorithm(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                OnlineLearnerTrainer(
                    split=_KnotStub(_config=KnotConfig(id="s")),
                    algorithm="",
                    monitor_metric="accuracy",
                    _config=KnotConfig(id="olt"),
                )

    def test_valid_construction(self) -> None:
        with Tapestry() as t:
            OnlineLearnerTrainer(
                split=_KnotStub(_config=KnotConfig(id="s")),
                algorithm="sgd",
                monitor_metric="accuracy",
                n_batches=20,
                _config=KnotConfig(id="olt"),
            )
        self.assertIsNotNone(t._store.get("olt"))
