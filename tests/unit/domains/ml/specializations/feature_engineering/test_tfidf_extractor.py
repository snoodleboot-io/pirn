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
from pirn.domains.ml.types.split_manifest import SplitManifest
from pirn.domains.ml.types.dataset_manifest import DatasetManifest
from pirn.tapestry import Tapestry


class _SplitSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> SplitManifest:
        ds = DatasetManifest(name="ds", feature_names=("text",), row_count=10)
        return SplitManifest(train=ds, test=ds)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> TFIDFExtractor:
        k = TFIDFExtractor.__new__(TFIDFExtractor)
        object.__setattr__(k, "_config", KnotConfig(id="tfidf"))
        return k

    def _make_split(self) -> SplitManifest:
        ds = DatasetManifest(name="ds", feature_names=("text",), row_count=10)
        return SplitManifest(train=ds, test=ds)

    async def test_rejects_empty_text_column(self) -> None:
        k = self._make_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                split=self._make_split(),
                text_column="",
                max_features=100,
            )

    async def test_rejects_max_features_less_than_1(self) -> None:
        k = self._make_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                split=self._make_split(),
                text_column="text",
                max_features=0,
            )

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
        self.assertIsInstance(split, SplitManifest)
        for i in range(3):
            self.assertIn(f"tfidf_{i}", split.train.feature_names)
