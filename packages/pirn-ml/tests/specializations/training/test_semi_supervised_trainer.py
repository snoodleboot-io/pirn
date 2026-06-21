"""Unit tests for :class:`SemiSupervisedTrainer`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry
from pirn_ml.specializations.training.semi_supervised_trainer import (
    SemiSupervisedTrainer,
)
from pirn_ml.types.dataset_manifest import DatasetManifest
from pirn_ml.types.split_manifest import SplitManifest


class _KnotStub(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> None:
        return None


def _make_knot() -> SemiSupervisedTrainer:
    with Tapestry():
        k = SemiSupervisedTrainer.__new__(SemiSupervisedTrainer)
        object.__setattr__(k, "_config", KnotConfig(id="sst"))
    return k


def _split() -> SplitManifest:
    ds = DatasetManifest(name="ds", feature_names=("x",), target_name="y", row_count=10, source_uri="mem://")
    return SplitManifest(train=ds, test=ds)


class TestSemiSupervisedTrainerValidation(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_negative_unlabeled_row_count(self) -> None:
        k = _make_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(split=_split(), algorithm="rf", unlabeled_row_count=-1, metrics=["accuracy"])

    async def test_rejects_non_int_unlabeled_row_count(self) -> None:
        k = _make_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(split=_split(), algorithm="rf", unlabeled_row_count=100.5, metrics=["accuracy"])  # type: ignore[arg-type]

    async def test_rejects_empty_metrics(self) -> None:
        k = _make_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(split=_split(), algorithm="rf", unlabeled_row_count=100, metrics=[])


class TestSemiSupervisedTrainerConstruction(unittest.TestCase):
    def test_valid_construction(self) -> None:
        with Tapestry() as t:
            SemiSupervisedTrainer(
                split=_KnotStub(_config=KnotConfig(id="s")),
                algorithm="rf",
                unlabeled_row_count=500,
                metrics=["accuracy"],
                _config=KnotConfig(id="sst"),
            )
        self.assertIsNotNone(t._store.get("sst"))
