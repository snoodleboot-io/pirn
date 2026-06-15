"""Unit tests for :class:`LagFeatureGenerator`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry
from pirn_ml.specializations.feature_engineering.lag_feature_generator import (
    LagFeatureGenerator,
)
from pirn_ml.types.dataset_manifest import DatasetManifest
from pirn_ml.types.split_manifest import SplitManifest


class _KnotStub(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> None:
        return None


class TestConstruction(unittest.TestCase):
    def test_valid_construction(self) -> None:
        with Tapestry() as t:
            LagFeatureGenerator(
                split=_KnotStub(_config=KnotConfig(id="s")),
                time_column="date",
                columns=["sales"],
                lags=[1, 7],
                _config=KnotConfig(id="lfg"),
            )
        self.assertIsNotNone(t._store.get("lfg"))


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> LagFeatureGenerator:
        k = LagFeatureGenerator.__new__(LagFeatureGenerator)
        object.__setattr__(k, "_config", KnotConfig(id="lfg"))
        return k

    def _make_split(self) -> SplitManifest:
        ds = DatasetManifest(name="ds", feature_names=("sales",), row_count=30)
        return SplitManifest(train=ds, test=ds)

    async def test_rejects_empty_columns(self) -> None:
        k = self._make_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                split=self._make_split(),
                time_column="date",
                columns=[],
                lags=[1],
            )

    async def test_rejects_empty_time_column(self) -> None:
        k = self._make_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                split=self._make_split(),
                time_column="",
                columns=["sales"],
                lags=[1],
            )
