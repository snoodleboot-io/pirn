"""Unit tests for :class:`TFIDFExtractor`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.ml.specializations.feature_engineering.tfidf_extractor import (
    TFIDFExtractor,
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
    def test_rejects_empty_text_column(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                TFIDFExtractor(
                    split=_SplitSource(_config=KnotConfig(id="s")),
                    text_column="",
                    _config=KnotConfig(id="tfidf"),
                )

    def test_rejects_max_features_less_than_1(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                TFIDFExtractor(
                    split=_SplitSource(_config=KnotConfig(id="s")),
                    text_column="text",
                    max_features=0,
                    _config=KnotConfig(id="tfidf"),
                )

    def test_max_features_attribute(self) -> None:
        with Tapestry():
            ext = TFIDFExtractor(
                split=_SplitSource(_config=KnotConfig(id="s")),
                text_column="text",
                max_features=50,
                _config=KnotConfig(id="tfidf"),
            )
        self.assertEqual(ext.max_features, 50)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_appends_tfidf_features(self) -> None:
        with Tapestry() as t:
            src = _SplitSource(_config=KnotConfig(id="src"))
            TFIDFExtractor(
                split=src,
                text_column="text",
                max_features=3,
                _config=KnotConfig(id="tfidf"),
            )
        result = await t.run(RunRequest())
        split = result.outputs["tfidf"]
        self.assertIsInstance(split, DataSplit)
        for i in range(3):
            self.assertIn(f"tfidf_{i}", split.train.feature_names)
