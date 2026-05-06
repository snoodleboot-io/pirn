"""Tests for :class:`FourierFeatureGenerator`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.feature_engineering.fourier_feature_generator import (
    FourierFeatureGenerator,
)
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.ml_dataset import MLDataset
from pirn.tapestry import Tapestry


@knot
async def emit_split() -> DataSplit:
    train = MLDataset(
        name="ts:train",
        feature_names=("hour_of_day",),
        target_name="y",
        row_count=100,
    )
    test = MLDataset(
        name="ts:test",
        feature_names=("hour_of_day",),
        target_name="y",
        row_count=25,
    )
    return DataSplit(train=train, test=test)


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    def _make_split(self) -> DataSplit:
        train = MLDataset(
            name="ts:train", feature_names=("hour_of_day",), target_name="y", row_count=100
        )
        test = MLDataset(
            name="ts:test", feature_names=("hour_of_day",), target_name="y", row_count=25
        )
        return DataSplit(train=train, test=test)

    async def test_rejects_empty_columns(self) -> None:
        with Tapestry():
            k = FourierFeatureGenerator.__new__(FourierFeatureGenerator)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(split=self._make_split(), columns=(), periods=(24,))

    async def test_rejects_period_below_two(self) -> None:
        with Tapestry():
            k = FourierFeatureGenerator.__new__(FourierFeatureGenerator)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(split=self._make_split(), columns=("hour_of_day",), periods=(1,))

    async def test_rejects_empty_periods(self) -> None:
        with Tapestry():
            k = FourierFeatureGenerator.__new__(FourierFeatureGenerator)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(split=self._make_split(), columns=("hour_of_day",), periods=())


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_appends_sin_cos_features(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            FourierFeatureGenerator(
                split=split,
                columns=("hour_of_day",),
                periods=(24,),
                _config=KnotConfig(id="ffg"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["ffg"]
        assert isinstance(out, DataSplit)
        features = out.train.feature_names
        assert "hour_of_day_sin_24" in features
        assert "hour_of_day_cos_24" in features
        assert "fourier" in out.train.name
