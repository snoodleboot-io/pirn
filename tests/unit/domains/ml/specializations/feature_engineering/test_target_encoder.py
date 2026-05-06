"""Unit tests for :class:`TargetEncoder`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.specializations.feature_engineering.target_encoder import (
    TargetEncoder,
)
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.ml_dataset import MLDataset
from pirn.tapestry import Tapestry


class _KnotStub(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> None:
        return None


class TestConstruction(unittest.TestCase):
    def test_valid_construction(self) -> None:
        with Tapestry() as t:
            TargetEncoder(
                split=_KnotStub(_config=KnotConfig(id="s")),
                categorical_column="cat",
                target_column="y",
                _config=KnotConfig(id="te"),
            )
        self.assertIsNotNone(t._store.get("te"))


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> TargetEncoder:
        k = TargetEncoder.__new__(TargetEncoder)
        object.__setattr__(k, "_config", KnotConfig(id="te"))
        return k

    def _make_split(self) -> DataSplit:
        ds = MLDataset(name="ds", feature_names=("cat", "y"), row_count=10)
        return DataSplit(train=ds, test=ds)

    async def test_rejects_empty_categorical_column(self) -> None:
        k = self._make_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                split=self._make_split(),
                categorical_column="",
                target_column="y",
                smoothing=1.0,
            )

    async def test_rejects_negative_smoothing(self) -> None:
        k = self._make_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                split=self._make_split(),
                categorical_column="cat",
                target_column="y",
                smoothing=-1.0,
            )

    async def test_rejects_empty_target_column(self) -> None:
        k = self._make_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                split=self._make_split(),
                categorical_column="cat",
                target_column="",
                smoothing=1.0,
            )
