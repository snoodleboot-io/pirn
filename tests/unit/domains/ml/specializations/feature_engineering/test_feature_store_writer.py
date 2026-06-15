"""Unit tests for :class:`FeatureStoreWriter`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry
from pirn_ml.feature_store_provider import FeatureStoreProvider
from pirn_ml.specializations.feature_engineering.feature_store_writer import (
    FeatureStoreWriter,
)


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
    def test_rejects_non_knot_split(self) -> None:
        with self.assertRaises(TypeError):
            with Tapestry():
                FeatureStoreWriter(
                    split="bad",  # type: ignore[arg-type]
                    feature_store=_StubStore(),
                    _config=KnotConfig(id="fsw"),
                )

    def test_rejects_wrong_store_type(self) -> None:
        with self.assertRaises(TypeError):
            with Tapestry():
                FeatureStoreWriter(
                    split=_KnotStub(_config=KnotConfig(id="s")),
                    feature_store="bad",  # type: ignore[arg-type]
                    _config=KnotConfig(id="fsw"),
                )

    def test_valid_construction(self) -> None:
        with Tapestry() as t:
            FeatureStoreWriter(
                split=_KnotStub(_config=KnotConfig(id="s")),
                feature_store=_StubStore(),
                _config=KnotConfig(id="fsw"),
            )
        self.assertIsNotNone(t._store.get("fsw"))
