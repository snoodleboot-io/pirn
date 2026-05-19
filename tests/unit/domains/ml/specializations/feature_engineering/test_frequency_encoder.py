"""Unit tests for :class:`FrequencyEncoder`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.specializations.feature_engineering.frequency_encoder import (
    FrequencyEncoder,
)
from pirn.domains.ml.types.split_manifest import SplitManifest
from pirn.domains.ml.types.dataset_manifest import DatasetManifest
from pirn.tapestry import Tapestry


class _KnotStub(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> None:
        return None


class TestConstruction(unittest.TestCase):
    def test_valid_construction(self) -> None:
        with Tapestry() as t:
            FrequencyEncoder(
                split=_KnotStub(_config=KnotConfig(id="s")),
                categorical_column="cat",
                _config=KnotConfig(id="fe"),
            )
        self.assertIsNotNone(t._store.get("fe"))


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> FrequencyEncoder:
        k = FrequencyEncoder.__new__(FrequencyEncoder)
        object.__setattr__(k, "_config", KnotConfig(id="fe"))
        return k

    def _make_split(self) -> SplitManifest:
        ds = DatasetManifest(name="ds", feature_names=("cat",), row_count=10)
        return SplitManifest(train=ds, test=ds)

    async def test_rejects_empty_categorical_column(self) -> None:
        k = self._make_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                split=self._make_split(),
                categorical_column="",
                default_frequency=0.0,
            )

    async def test_rejects_negative_default_frequency(self) -> None:
        k = self._make_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                split=self._make_split(),
                categorical_column="cat",
                default_frequency=-0.1,
            )
