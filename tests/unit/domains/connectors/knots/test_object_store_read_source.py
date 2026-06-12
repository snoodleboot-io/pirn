"""Tests for :class:`ObjectStoreReadSource` calling process() directly."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pirn.core.knot_config import KnotConfig
from pirn.connectors.knots.object_store_knot import ObjectStoreKnot
from pirn.connectors.knots.object_store_read_source import ObjectStoreReadSource
from pirn.connectors.object_storage.local_filesystem_config import LocalFilesystemConfig
from pirn.connectors.object_storage.local_filesystem_store import LocalFilesystemStore


class TestObjectStoreReadSource(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmp.name)
        self.store = LocalFilesystemStore(LocalFilesystemConfig(root=self.tmp_path))
        store_knot = ObjectStoreKnot(store=self.store, _config=KnotConfig(id="store"))
        self.source = ObjectStoreReadSource(
            store=store_knot,
            key="placeholder",
            _config=KnotConfig(id="read"),
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    async def test_reads_bytes_from_store(self) -> None:
        await self.store.put("greeting.txt", b"hello, pirn")
        result = await self.source.process(store=self.store, key="greeting.txt")
        assert result == b"hello, pirn"

    async def test_streams_large_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalFilesystemStore(LocalFilesystemConfig(root=Path(tmp), chunk_size=64))
            payload = b"x" * 4096
            await store.put("big.bin", payload)
            store_knot = ObjectStoreKnot(store=store, _config=KnotConfig(id="store2"))
            source = ObjectStoreReadSource(
                store=store_knot,
                key="big.bin",
                _config=KnotConfig(id="big"),
            )
            result = await source.process(store=store, key="big.bin")
            assert result == payload

    async def test_rejects_non_object_store(self) -> None:
        with self.assertRaises(TypeError) as ctx:
            await self.source.process(store=object(), key="x")  # type: ignore[arg-type]
        assert "ObjectStore" in str(ctx.exception)

    async def test_rejects_empty_key(self) -> None:
        with self.assertRaises(ValueError):
            await self.source.process(store=self.store, key="")
