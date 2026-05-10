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


def _make_knot() -> OnlineLearnerTrainer:
    with Tapestry():
        k = OnlineLearnerTrainer.__new__(OnlineLearnerTrainer)
        object.__setattr__(k, "_config", KnotConfig(id="olt"))
    return k


def _split():
    from pirn.domains.ml.types.split_manifest import SplitManifest
    from pirn.domains.ml.types.dataset_manifest import DatasetManifest

    return SplitManifest(
        train=DatasetManifest(name="tr", feature_names=["x"], target_name="y", row_count=10, source_uri="mem://"),
        test=DatasetManifest(name="te", feature_names=["x"], target_name="y", row_count=5, source_uri="mem://"),
    )


class TestOnlineLearnerTrainerValidation(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_n_batches_less_than_1(self) -> None:
        k = _make_knot()
        with self.assertRaises((ValueError, TypeError)):
            await k.process(split=_split(), algorithm="sgd", monitor_metric="accuracy", n_batches=0)

    async def test_rejects_empty_monitor_metric(self) -> None:
        k = _make_knot()
        with self.assertRaises((ValueError, TypeError)):
            await k.process(split=_split(), algorithm="sgd", monitor_metric="")

    async def test_rejects_empty_algorithm(self) -> None:
        k = _make_knot()
        with self.assertRaises((ValueError, TypeError)):
            await k.process(split=_split(), algorithm="", monitor_metric="accuracy")


class TestOnlineLearnerTrainerConstruction(unittest.TestCase):
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
