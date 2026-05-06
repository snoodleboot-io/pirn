"""Unit tests for :class:`BaggingEnsembleBuilder`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.specializations.training.bagging_ensemble_builder import (
    BaggingEnsembleBuilder,
)
from pirn.tapestry import Tapestry


class _KnotStub(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> None:
        return None


def _make_knot() -> BaggingEnsembleBuilder:
    with Tapestry():
        k = BaggingEnsembleBuilder.__new__(BaggingEnsembleBuilder)
        object.__setattr__(k, "_config", KnotConfig(id="beb"))
    return k


class TestBaggingEnsembleBuilderValidation(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_n_estimators_less_than_2(self) -> None:
        from pirn.domains.ml.types.data_split import DataSplit
        from pirn.domains.ml.types.ml_dataset import MLDataset

        split = DataSplit(
            train=MLDataset(name="tr", feature_names=["x"], target_name="y", row_count=10, source_uri="mem://"),
            test=MLDataset(name="te", feature_names=["x"], target_name="y", row_count=5, source_uri="mem://"),
        )
        k = _make_knot()
        with self.assertRaises((ValueError, TypeError)):
            await k.process(split=split, algorithm="dt", n_estimators=1, metrics=["accuracy"])

    async def test_rejects_invalid_task(self) -> None:
        from pirn.domains.ml.types.data_split import DataSplit
        from pirn.domains.ml.types.ml_dataset import MLDataset

        split = DataSplit(
            train=MLDataset(name="tr", feature_names=["x"], target_name="y", row_count=10, source_uri="mem://"),
            test=MLDataset(name="te", feature_names=["x"], target_name="y", row_count=5, source_uri="mem://"),
        )
        k = _make_knot()
        with self.assertRaises((ValueError, TypeError)):
            await k.process(split=split, algorithm="dt", task="clustering", metrics=["accuracy"])

    async def test_rejects_empty_algorithm(self) -> None:
        from pirn.domains.ml.types.data_split import DataSplit
        from pirn.domains.ml.types.ml_dataset import MLDataset

        split = DataSplit(
            train=MLDataset(name="tr", feature_names=["x"], target_name="y", row_count=10, source_uri="mem://"),
            test=MLDataset(name="te", feature_names=["x"], target_name="y", row_count=5, source_uri="mem://"),
        )
        k = _make_knot()
        with self.assertRaises((ValueError, TypeError)):
            await k.process(split=split, algorithm="", metrics=["accuracy"])


class TestBaggingEnsembleBuilderConstruction(unittest.TestCase):
    def test_valid_construction(self) -> None:
        with Tapestry() as t:
            BaggingEnsembleBuilder(
                split=_KnotStub(_config=KnotConfig(id="s")),
                algorithm="dt",
                n_estimators=5,
                task="classification",
                metrics=["accuracy"],
                _config=KnotConfig(id="beb"),
            )
        self.assertIsNotNone(t._store.get("beb"))
