"""Unit tests for :class:`HashEncoder`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.feature_engineering.hash_encoder import (
    HashEncoder,
)
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.ml_dataset import MLDataset
from pirn.tapestry import Tapestry


class _SplitSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> DataSplit:
        ds = MLDataset(name="ds", feature_names=("cat_col",), row_count=10)
        return DataSplit(train=ds, test=ds)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> HashEncoder:
        k = HashEncoder.__new__(HashEncoder)
        object.__setattr__(k, "_config", KnotConfig(id="he"))
        return k

    def _make_split(self) -> DataSplit:
        ds = MLDataset(name="ds", feature_names=("cat_col",), row_count=10)
        return DataSplit(train=ds, test=ds)

    async def test_rejects_empty_categorical_column(self) -> None:
        k = self._make_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                split=self._make_split(),
                categorical_column="",
                n_components=8,
            )

    async def test_rejects_n_components_less_than_1(self) -> None:
        k = self._make_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                split=self._make_split(),
                categorical_column="cat_col",
                n_components=0,
            )

    async def test_appends_hash_features(self) -> None:
        with Tapestry() as t:
            src = _SplitSource(_config=KnotConfig(id="src"))
            HashEncoder(
                split=src,
                categorical_column="cat_col",
                n_components=4,
                _config=KnotConfig(id="he"),
            )
        result = await t.run(RunRequest())
        split = result.outputs["he"]
        self.assertIsInstance(split, DataSplit)
        for i in range(4):
            self.assertIn(f"cat_col_hash_{i}", split.train.feature_names)
