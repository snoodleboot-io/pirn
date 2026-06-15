"""Tests for :class:`LagFeatureGenerator`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.feature_engineering.lag_feature_generator import (
    LagFeatureGenerator,
)
from pirn.domains.ml.types.dataset_manifest import DatasetManifest
from pirn.domains.ml.types.split_manifest import SplitManifest
from pirn.tapestry import Tapestry


@knot
async def emit_split() -> SplitManifest:
    train = DatasetManifest(
        name="ts:train",
        feature_names=("t", "value"),
        target_name="y",
        row_count=80,
    )
    test = DatasetManifest(
        name="ts:test",
        feature_names=("t", "value"),
        target_name="y",
        row_count=20,
    )
    return SplitManifest(train=train, test=test)


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    def _make_split(self) -> SplitManifest:
        train = DatasetManifest(
            name="ts:train", feature_names=("t", "value"), target_name="y", row_count=80
        )
        test = DatasetManifest(
            name="ts:test", feature_names=("t", "value"), target_name="y", row_count=20
        )
        return SplitManifest(train=train, test=test)

    async def test_rejects_empty_columns(self) -> None:
        with Tapestry():
            k = LagFeatureGenerator.__new__(LagFeatureGenerator)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(split=self._make_split(), time_column="t", columns=())

    async def test_rejects_lag_below_one(self) -> None:
        with Tapestry():
            k = LagFeatureGenerator.__new__(LagFeatureGenerator)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                split=self._make_split(), time_column="t", columns=("value",), lags=(0,)
            )


class TestHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_appends_lag_feature_names(self) -> None:
        with Tapestry() as t:
            split = emit_split(_config=KnotConfig(id="split"))
            LagFeatureGenerator(
                split=split,
                time_column="t",
                columns=("value",),
                lags=(1, 7),
                _config=KnotConfig(id="lag"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs["lag"]
        assert isinstance(out, SplitManifest)
        assert "value_lag_1" in out.train.feature_names
        assert "value_lag_7" in out.train.feature_names
        assert "value_lag_1" in out.test.feature_names
