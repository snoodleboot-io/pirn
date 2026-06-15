"""Unit tests for :class:`RollingStatisticsGenerator`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.feature_engineering.rolling_statistics_generator import (
    RollingStatisticsGenerator,
)
from pirn.domains.ml.types.dataset_manifest import DatasetManifest
from pirn.domains.ml.types.split_manifest import SplitManifest
from pirn.tapestry import Tapestry


class _SplitSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> SplitManifest:
        ds = DatasetManifest(name="ds", feature_names=("price",), row_count=30)
        return SplitManifest(train=ds, test=ds)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> RollingStatisticsGenerator:
        k = RollingStatisticsGenerator.__new__(RollingStatisticsGenerator)
        object.__setattr__(k, "_config", KnotConfig(id="rsg"))
        return k

    def _make_split(self) -> SplitManifest:
        ds = DatasetManifest(name="ds", feature_names=("price",), row_count=30)
        return SplitManifest(train=ds, test=ds)

    async def test_rejects_invalid_statistic(self) -> None:
        k = self._make_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                split=self._make_split(),
                columns=["price"],
                windows=[7],
                statistics=["median"],
            )

    async def test_rejects_window_less_than_1(self) -> None:
        k = self._make_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                split=self._make_split(),
                columns=["price"],
                windows=[0],
                statistics=["mean"],
            )

    async def test_rejects_empty_columns(self) -> None:
        k = self._make_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                split=self._make_split(),
                columns=[],
                windows=[7],
                statistics=["mean"],
            )

    async def test_appends_rolling_stat_features(self) -> None:
        with Tapestry() as t:
            src = _SplitSource(_config=KnotConfig(id="src"))
            RollingStatisticsGenerator(
                split=src,
                columns=["price"],
                windows=[7],
                statistics=["mean"],
                _config=KnotConfig(id="rsg"),
            )
        result = await t.run(RunRequest())
        split = result.outputs["rsg"]
        self.assertIsInstance(split, SplitManifest)
        self.assertIn("price_roll7_mean", split.train.feature_names)
