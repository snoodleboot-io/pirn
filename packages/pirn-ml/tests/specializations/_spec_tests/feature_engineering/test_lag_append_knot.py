"""Tests for :class:`LagAppendKnot`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_ml.specializations.feature_engineering.lag_append_knot import (
    LagAppendKnot,
)
from pirn_ml.types.dataset_manifest import DatasetManifest
from pirn_ml.types.split_manifest import SplitManifest


def _split_fixture() -> SplitManifest:
    train = DatasetManifest(name="d:train", feature_names=("value",), row_count=80)
    test = DatasetManifest(name="d:test", feature_names=("value",), row_count=20)
    return SplitManifest(train=train, test=test)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_time_column(self) -> None:
        with Tapestry():
            k = LagAppendKnot.__new__(LagAppendKnot)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                split=_split_fixture(),
                time_column="",
                columns=("value",),
                lags=(1, 2),
            )

    async def test_rejects_empty_columns(self) -> None:
        with Tapestry():
            k = LagAppendKnot.__new__(LagAppendKnot)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                split=_split_fixture(),
                time_column="ts",
                columns=(),
                lags=(1, 2),
            )

    async def test_rejects_empty_lags(self) -> None:
        with Tapestry():
            k = LagAppendKnot.__new__(LagAppendKnot)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                split=_split_fixture(),
                time_column="ts",
                columns=("value",),
                lags=(),
            )
