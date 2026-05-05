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


class TestConstruction(unittest.TestCase):
    def test_rejects_invalid_analyzer(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                NGramExtractor(
                    split=_SplitSource(_config=KnotConfig(id="s")),
                    text_column="text",
                    analyzer="sentence",
                    _config=KnotConfig(id="ng"),
                )

    def test_rejects_n_less_than_1(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                NGramExtractor(
                    split=_SplitSource(_config=KnotConfig(id="s")),
                    text_column="text",
                    n=0,
                    _config=KnotConfig(id="ng"),
                )

    def test_rejects_max_features_less_than_1(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                NGramExtractor(
                    split=_SplitSource(_config=KnotConfig(id="s")),
                    text_column="text",
                    max_features=0,
                    _config=KnotConfig(id="ng"),
                )

    def test_attributes_stored(self) -> None:
        with Tapestry():
            ng = NGramExtractor(
                split=_SplitSource(_config=KnotConfig(id="s")),
                text_column="text",
                n=3,
                analyzer="char",
                max_features=20,
                _config=KnotConfig(id="ng"),
            )
        self.assertEqual(ng.n, 3)
        self.assertEqual(ng.analyzer, "char")
