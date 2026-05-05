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
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.ml_dataset import MLDataset
from pirn.tapestry import Tapestry


class _SplitSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> DataSplit:
        ds = MLDataset(name="ds", feature_names=("price",), row_count=30)
        return DataSplit(train=ds, test=ds)


class TestConstruction(unittest.TestCase):
    def test_rejects_invalid_statistic(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                RollingStatisticsGenerator(
                    split=_SplitSource(_config=KnotConfig(id="s")),
                    columns=["price"],
                    statistics=["median"],
                    _config=KnotConfig(id="rsg"),
                )

    def test_rejects_window_less_than_1(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                RollingStatisticsGenerator(
                    split=_SplitSource(_config=KnotConfig(id="s")),
                    columns=["price"],
                    windows=[0],
                    _config=KnotConfig(id="rsg"),
                )

    def test_rejects_empty_columns(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                RollingStatisticsGenerator(
                    split=_SplitSource(_config=KnotConfig(id="s")),
                    columns=[],
                    _config=KnotConfig(id="rsg"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
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
        self.assertIsInstance(split, DataSplit)
        self.assertIn("price_roll7_mean", split.train.feature_names)
