"""Tests for :class:`FeatureStoreProvider`."""

from __future__ import annotations

import pytest

from pirn.domains.ml.feature_store_provider import FeatureStoreProvider


class TestFeatureStoreProviderInterface:
    async def test_get_features_raises_not_implemented(self) -> None:
        provider = FeatureStoreProvider()
        with pytest.raises(NotImplementedError, match="get_features"):
            await provider.get_features([{"id": 1}], ["a"])

    async def test_write_features_raises_not_implemented(self) -> None:
        provider = FeatureStoreProvider()
        with pytest.raises(NotImplementedError, match="write_features"):
            await provider.write_features([{"a": 1}])

    async def test_close_raises_not_implemented(self) -> None:
        provider = FeatureStoreProvider()
        with pytest.raises(NotImplementedError, match="close"):
            await provider.close()
