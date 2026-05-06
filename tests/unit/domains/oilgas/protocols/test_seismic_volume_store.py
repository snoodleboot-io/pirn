"""Tests for :class:`SeismicVolumeStore` interface contract."""

from __future__ import annotations

import unittest

from pirn.domains.oilgas.protocols.seismic_volume_store import SeismicVolumeStore


class TestSeismicVolumeStoreInterface(unittest.IsolatedAsyncioTestCase):
    async def test_fetch_volume_raises_not_implemented(self) -> None:
        with self.assertRaisesRegex(NotImplementedError, "fetch_volume"):
            await SeismicVolumeStore().fetch_volume("vol-1")

    async def test_close_raises_not_implemented(self) -> None:
        with self.assertRaisesRegex(NotImplementedError, "close"):
            await SeismicVolumeStore().close()

    async def test_subclass_name_in_message(self) -> None:
        class MyStore(SeismicVolumeStore):
            pass

        with self.assertRaisesRegex(NotImplementedError, "MyStore"):
            await MyStore().fetch_volume("v")
