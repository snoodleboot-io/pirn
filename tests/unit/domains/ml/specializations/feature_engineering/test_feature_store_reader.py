"""Unit tests for :class:`FeatureStoreReader`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.feature_store_provider import FeatureStoreProvider
from pirn.domains.ml.specializations.feature_engineering.feature_store_reader import (
    FeatureStoreReader,
)
from pirn.tapestry import Tapestry


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
    def test_rejects_empty_entity_keys(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                FeatureStoreReader(
                    split=_KnotStub(_config=KnotConfig(id="s")),
                    feature_store=_StubStore(),
                    entity_keys=[],
                    feature_names=["f1"],
                    _config=KnotConfig(id="fsr"),
                )

    def test_rejects_empty_feature_names(self) -> None:
        with self.assertRaises(ValueError):
            with Tapestry():
                FeatureStoreReader(
                    split=_KnotStub(_config=KnotConfig(id="s")),
                    feature_store=_StubStore(),
                    entity_keys=["id"],
                    feature_names=[],
                    _config=KnotConfig(id="fsr"),
                )

    def test_rejects_wrong_store_type(self) -> None:
        with self.assertRaises(TypeError):
            with Tapestry():
                FeatureStoreReader(
                    split=_KnotStub(_config=KnotConfig(id="s")),
                    feature_store="bad",  # type: ignore[arg-type]
                    entity_keys=["id"],
                    feature_names=["f1"],
                    _config=KnotConfig(id="fsr"),
                )

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
