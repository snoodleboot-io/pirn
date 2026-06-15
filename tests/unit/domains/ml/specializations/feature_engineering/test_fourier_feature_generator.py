"""Unit tests for :class:`FourierFeatureGenerator`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.feature_engineering.fourier_feature_generator import (
    FourierFeatureGenerator,
)
from pirn.domains.ml.types.dataset_manifest import DatasetManifest
from pirn.domains.ml.types.split_manifest import SplitManifest
from pirn.tapestry import Tapestry


class _SplitSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> SplitManifest:
        ds = DatasetManifest(name="ds", feature_names=("hour",), row_count=100)
        return SplitManifest(train=ds, test=ds)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> FourierFeatureGenerator:
        k = FourierFeatureGenerator.__new__(FourierFeatureGenerator)
        object.__setattr__(k, "_config", KnotConfig(id="ffg"))
        return k

    def _make_split(self) -> SplitManifest:
        ds = DatasetManifest(name="ds", feature_names=("hour",), row_count=100)
        return SplitManifest(train=ds, test=ds)

    async def test_rejects_empty_columns(self) -> None:
        k = self._make_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(split=self._make_split(), columns=[], periods=[24])

    async def test_rejects_period_less_than_2(self) -> None:
        k = self._make_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(split=self._make_split(), columns=["hour"], periods=[1])

    async def test_rejects_non_int_period(self) -> None:
        k = self._make_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                split=self._make_split(),
                columns=["hour"],
                periods=[24.0],  # type: ignore[list-item]
            )

    async def test_appends_sin_cos_features(self) -> None:
        with Tapestry() as t:
            src = _SplitSource(_config=KnotConfig(id="src"))
            FourierFeatureGenerator(
                split=src,
                columns=["hour"],
                periods=[24],
                _config=KnotConfig(id="ffg"),
            )
        result = await t.run(RunRequest())
        split = result.outputs["ffg"]
        self.assertIsInstance(split, SplitManifest)
        self.assertIn("hour_sin_24", split.train.feature_names)
        self.assertIn("hour_cos_24", split.train.feature_names)
