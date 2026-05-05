"""Unit tests for :class:`FeatureStoreProvider`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.domains.ml.feature_store_provider import FeatureStoreProvider


class _StubStore(FeatureStoreProvider):
    async def get_features(self, entity_keys, feature_names):
        return [dict.fromkeys(feature_names, 0.0) for _ in entity_keys]

    async def write_features(self, features) -> int:
        return sum(1 for _ in features)

    async def close(self) -> None:
        pass


class TestFeatureStoreProviderInterface(unittest.IsolatedAsyncioTestCase):
    async def test_base_get_features_raises(self) -> None:
        store = FeatureStoreProvider()
        with self.assertRaises(NotImplementedError):
            await store.get_features([{"id": "1"}], ["f1"])

    async def test_base_write_features_raises(self) -> None:
        store = FeatureStoreProvider()
        with self.assertRaises(NotImplementedError):
            await store.write_features([{"f1": 1.0}])

    async def test_base_close_raises(self) -> None:
        store = FeatureStoreProvider()
        with self.assertRaises(NotImplementedError):
            await store.close()

    def test_clear_credentials_nullifies_config(self) -> None:
        store = FeatureStoreProvider()
        store._config = {"token": "abc"}  # type: ignore[assignment]
        store._clear_credentials()
        self.assertIsNone(store._config)

    async def test_subclass_get_features_returns_rows(self) -> None:
        store = _StubStore()
        rows = await store.get_features([{"id": "1"}], ["a", "b"])
        self.assertEqual(len(rows), 1)
        self.assertIn("a", rows[0])

    async def test_subclass_write_features_returns_count(self) -> None:
        store = _StubStore()
        count = await store.write_features([{"a": 1}, {"a": 2}])
        self.assertEqual(count, 2)
