"""Unit tests for :class:`NGramExtractor`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.feature_engineering.ngram_extractor import (
    NGramExtractor,
)
from pirn.domains.ml.types.data_split import DataSplit
from pirn.domains.ml.types.ml_dataset import MLDataset
from pirn.tapestry import Tapestry


class _SplitSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> DataSplit:
        ds = MLDataset(name="ds", feature_names=("text",), row_count=10)
        return DataSplit(train=ds, test=ds)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> NGramExtractor:
        k = NGramExtractor.__new__(NGramExtractor)
        object.__setattr__(k, "_config", KnotConfig(id="ng"))
        return k

    def _make_split(self) -> DataSplit:
        ds = MLDataset(name="ds", feature_names=("text",), row_count=10)
        return DataSplit(train=ds, test=ds)

    async def test_rejects_invalid_analyzer(self) -> None:
        k = self._make_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                split=self._make_split(),
                text_column="text",
                n=2,
                analyzer="sentence",
                max_features=50,
            )

    async def test_rejects_n_less_than_1(self) -> None:
        k = self._make_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                split=self._make_split(),
                text_column="text",
                n=0,
                analyzer="word",
                max_features=50,
            )

    async def test_rejects_max_features_less_than_1(self) -> None:
        k = self._make_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                split=self._make_split(),
                text_column="text",
                n=2,
                analyzer="word",
                max_features=0,
            )
