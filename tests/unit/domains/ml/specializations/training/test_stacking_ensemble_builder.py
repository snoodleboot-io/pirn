"""Unit tests for :class:`StackingEnsembleBuilder`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry
from pirn_ml.specializations.training.stacking_ensemble_builder import (
    StackingEnsembleBuilder,
)
from pirn_ml.types.dataset_manifest import DatasetManifest
from pirn_ml.types.split_manifest import SplitManifest


class _KnotStub(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> None:
        return None


def _make_knot() -> StackingEnsembleBuilder:
    with Tapestry():
        k = StackingEnsembleBuilder.__new__(StackingEnsembleBuilder)
        object.__setattr__(k, "_config", KnotConfig(id="seb"))
    return k


def _split() -> SplitManifest:
    ds = DatasetManifest(name="ds", feature_names=("x",), target_name="y", row_count=10, source_uri="mem://")
    return SplitManifest(train=ds, test=ds)


class TestStackingEnsembleBuilderValidation(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_fewer_than_two_base_algorithms(self) -> None:
        k = _make_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                split=_split(),
                base_algorithms=["rf"],
                meta_algorithm="logistic",
                metrics=["accuracy"],
            )

    async def test_rejects_empty_meta_algorithm(self) -> None:
        k = _make_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                split=_split(),
                base_algorithms=["rf", "xgb"],
                meta_algorithm="",
                metrics=["accuracy"],
            )

    async def test_rejects_empty_metrics(self) -> None:
        k = _make_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                split=_split(),
                base_algorithms=["rf", "xgb"],
                meta_algorithm="logistic",
                metrics=[],
            )


class TestStackingEnsembleBuilderConstruction(unittest.TestCase):
    def test_valid_construction(self) -> None:
        with Tapestry() as t:
            StackingEnsembleBuilder(
                split=_KnotStub(_config=KnotConfig(id="s")),
                base_algorithms=["rf", "xgb"],
                meta_algorithm="logistic",
                metrics=["accuracy"],
                _config=KnotConfig(id="seb"),
            )
        self.assertIsNotNone(t._store.get("seb"))
