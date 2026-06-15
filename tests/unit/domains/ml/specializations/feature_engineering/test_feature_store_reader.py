"""Unit tests for :class:`FeatureStoreReader`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry
from pirn_ml.feature_store_provider import FeatureStoreProvider
from pirn_ml.specializations.feature_engineering.feature_store_reader import (
    FeatureStoreReader,
)
from pirn_ml.types.dataset_manifest import DatasetManifest
from pirn_ml.types.split_manifest import SplitManifest


class _StubStore(FeatureStoreProvider):
    async def get_features(self, entity_keys, feature_names):
        return []

    async def write_features(self, features) -> int:
        return 0

    async def close(self) -> None:
        pass


class _KnotStub(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> None:
        return None


class TestConstruction(unittest.TestCase):
    def test_valid_construction(self) -> None:
        with Tapestry() as t:
            FeatureStoreReader(
                split=_KnotStub(_config=KnotConfig(id="s")),
                feature_store=_StubStore(),
                entity_keys=["id"],
                feature_names=["f1"],
                _config=KnotConfig(id="fsr"),
            )
        self.assertIsNotNone(t._store.get("fsr"))


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> FeatureStoreReader:
        k = FeatureStoreReader.__new__(FeatureStoreReader)
        object.__setattr__(k, "_config", KnotConfig(id="fsr"))
        return k

    def _make_split(self) -> SplitManifest:
        ds = DatasetManifest(name="ds", feature_names=("id",), row_count=1)
        return SplitManifest(train=ds, test=ds)

    async def test_rejects_empty_entity_keys(self) -> None:
        k = self._make_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                split=self._make_split(),
                feature_store=_StubStore(),
                entity_keys=[],
                feature_names=["f1"],
            )

    async def test_rejects_empty_feature_names(self) -> None:
        k = self._make_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                split=self._make_split(),
                feature_store=_StubStore(),
                entity_keys=["id"],
                feature_names=[],
            )

    async def test_rejects_wrong_store_type(self) -> None:
        k = self._make_knot()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                split=self._make_split(),
                feature_store="bad",  # type: ignore[arg-type]
                entity_keys=["id"],
                feature_names=["f1"],
            )
