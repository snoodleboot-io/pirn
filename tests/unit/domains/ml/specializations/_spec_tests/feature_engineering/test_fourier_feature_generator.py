"""Tests for :class:`FourierFeatureGenerator`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_ml.specializations.feature_engineering.fourier_feature_generator import (
    FourierFeatureGenerator,
)
from pirn_ml.types.dataset_manifest import DatasetManifest
from pirn_ml.types.split_manifest import SplitManifest


@knot
async def emit_split() -> SplitManifest:
    train = DatasetManifest(
        name="ts:train",
        feature_names=("hour_of_day",),
        target_name="y",
        row_count=100,
    )
    test = DatasetManifest(
        name="ts:test",
        feature_names=("hour_of_day",),
        target_name="y",
        row_count=25,
    )
    return SplitManifest(train=train, test=test)


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    def _make_split(self) -> SplitManifest:
        train = DatasetManifest(
            name="ts:train", feature_names=("hour_of_day",), target_name="y", row_count=100
        )
        test = DatasetManifest(
            name="ts:test", feature_names=("hour_of_day",), target_name="y", row_count=25
        )
        return SplitManifest(train=train, test=test)

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
        assert isinstance(out, SplitManifest)
        features = out.train.feature_names
        assert "hour_of_day_sin_24" in features
        assert "hour_of_day_cos_24" in features
        assert "fourier" in out.train.name
