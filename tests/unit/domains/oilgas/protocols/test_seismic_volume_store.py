"""Tests for :class:`SeismicVolumeStore` interface contract."""

from __future__ import annotations

import pytest

from pirn.domains.oilgas.protocols.seismic_volume_store import SeismicVolumeStore


@pytest.mark.asyncio
class TestSeismicVolumeStoreInterface:
    async def test_fetch_volume_raises_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError, match="fetch_volume"):
            await SeismicVolumeStore().fetch_volume("vol-1")

    async def test_close_raises_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError, match="close"):
            await SeismicVolumeStore().close()

    async def test_subclass_name_in_message(self) -> None:
        class MyStore(SeismicVolumeStore):
            pass

        with pytest.raises(NotImplementedError, match="MyStore"):
            await MyStore().fetch_volume("v")
