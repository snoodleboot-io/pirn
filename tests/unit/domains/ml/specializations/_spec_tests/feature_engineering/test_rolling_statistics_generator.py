"""Tests for :class:`RollingStatisticsGenerator`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.feature_engineering.rolling_statistics_generator import (
    RollingStatisticsGenerator,
)
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.ml_dataset import MLDataset
from pirn.tapestry import Tapestry


@knot
async def emit_split() -> DataSplit:
    train = MLDataset(
        name="ts:train", feature_names=("sales",), target_name="y", row_count=200
    )
    test = MLDataset(
        name="ts:test", feature_names=("sales",), target_name="y", row_count=50
    )
    return DataSplit(train=train, test=test)


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    def _make_split(self) -> DataSplit:
        train = MLDataset(
            name="ts:train", feature_names=("sales",), target_name="y", row_count=200
        )
        test = MLDataset(
            name="ts:test", feature_names=("sales",), target_name="y", row_count=50
        )
        return DataSplit(train=train, test=test)

    async def test_rejects_empty_columns(self) -> None:
        with Tapestry():
            k = RollingStatisticsGenerator.__new__(RollingStatisticsGenerator)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(split=self._make_split(), columns=())

    async def test_rejects_window_below_one(self) -> None:
        with Tapestry():
            k = RollingStatisticsGenerator.__new__(RollingStatisticsGenerator)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(split=self._make_split(), columns=("sales",), windows=(0,))

    async def test_rejects_invalid_statistic(self) -> None:
        with Tapestry():
            k = RollingStatisticsGenerator.__new__(RollingStatisticsGenerator)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                split=self._make_split(), columns=("sales",), statistics=("median",)
            )


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_appends_rolling_feature_names(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            RollingStatisticsGenerator(
                split=split,
                columns=("sales",),
                windows=(7,),
                statistics=("mean", "std"),
                _config=KnotConfig(id="rsg"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["rsg"]
        assert isinstance(out, DataSplit)
        features = out.train.feature_names
        assert "sales_roll7_mean" in features
        assert "sales_roll7_std" in features
        assert "sales" in features
        assert "rolling_stats" in out.train.name
