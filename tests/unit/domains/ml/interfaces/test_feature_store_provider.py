"""Tests for :class:`FeatureStoreProvider`."""

from __future__ import annotations

import unittest

from pirn_ml.feature_store_provider import FeatureStoreProvider


class TestFeatureStoreProviderInterface(unittest.IsolatedAsyncioTestCase):
    async def test_get_features_raises_not_implemented(self) -> None:
        provider = FeatureStoreProvider()
        with self.assertRaisesRegex(NotImplementedError, "get_features"):
            await provider.get_features([{"id": 1}], ["a"])

    async def test_write_features_raises_not_implemented(self) -> None:
        provider = FeatureStoreProvider()
        with self.assertRaisesRegex(NotImplementedError, "write_features"):
            await provider.write_features([{"a": 1}])

    async def test_close_raises_not_implemented(self) -> None:
        provider = FeatureStoreProvider()
        with self.assertRaisesRegex(NotImplementedError, "close"):
            await provider.close()
