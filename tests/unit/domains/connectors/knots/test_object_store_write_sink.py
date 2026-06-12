"""Tests for :class:`ObjectStoreWriteSink` calling process() directly."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pirn.core.knot_config import KnotConfig
from pirn.connectors.knots.object_store_knot import ObjectStoreKnot
from pirn.connectors.knots.object_store_write_sink import ObjectStoreWriteSink
from pirn.connectors.object_storage.local_filesystem_config import LocalFilesystemConfig
from pirn.connectors.object_storage.local_filesystem_store import LocalFilesystemStore


class TestObjectStoreWriteSink(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmp.name)
        self.store = LocalFilesystemStore(LocalFilesystemConfig(root=self.tmp_path))
        store_knot = ObjectStoreKnot(store=self.store, _config=KnotConfig(id="store"))
        self.sink = ObjectStoreWriteSink(
            store=store_knot,
            key="placeholder",
            body=store_knot,  # dummy knot for wiring; process() called directly
            _config=KnotConfig(id="sink"),
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    async def test_writes_bytes_to_store(self) -> None:
        await self.sink.process(store=self.store, key="out/result.bin", body=b"persisted by pirn")
        written = (self.tmp_path / "out" / "result.bin").read_bytes()
        assert written == b"persisted by pirn"

    async def test_accepts_bytearray(self) -> None:
        await self.sink.process(store=self.store, key="ba.bin", body=bytearray(b"hello"))
        written = (self.tmp_path / "ba.bin").read_bytes()
        assert written == b"hello"

    async def test_rejects_non_bytes_body(self) -> None:
        with self.assertRaises(TypeError) as ctx:
            await self.sink.process(
                store=self.store,
                key="x.bin",
                body="not bytes",  # type: ignore[arg-type]
            )
        assert "body must be bytes" in str(ctx.exception)

    async def test_rejects_non_object_store(self) -> None:
        with self.assertRaises(TypeError) as ctx:
            await self.sink.process(
                store=object(),  # type: ignore[arg-type]
                key="x",
                body=b"data",
            )
        assert "ObjectStore" in str(ctx.exception)

    async def test_rejects_empty_key(self) -> None:
        with self.assertRaises(ValueError):
            await self.sink.process(store=self.store, key="", body=b"data")
