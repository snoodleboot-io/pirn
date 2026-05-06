"""Tests for :class:`ObjectStoreListSource` calling process() directly."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.knots.object_store_knot import ObjectStoreKnot
from pirn.domains.connectors.knots.object_store_list_source import ObjectStoreListSource
from pirn.domains.connectors.object_storage.local_filesystem_config import LocalFilesystemConfig
from pirn.domains.connectors.object_storage.local_filesystem_store import LocalFilesystemStore


class TestObjectStoreListSource(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmp.name)
        self.store = LocalFilesystemStore(LocalFilesystemConfig(root=self.tmp_path))
        store_knot = ObjectStoreKnot(store=self.store, _config=KnotConfig(id="store"))
        self.source = ObjectStoreListSource(
            store=store_knot,
            prefix="",
            _config=KnotConfig(id="list"),
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    async def test_lists_keys_under_prefix(self) -> None:
        await self.store.put("users/alice.json", b"{}")
        await self.store.put("users/bob.json", b"{}")
        await self.store.put("orders/1.json", b"{}")

        keys = await self.source.process(store=self.store, prefix="users/")
        assert keys == ["users/alice.json", "users/bob.json"]

    async def test_lists_all_keys_with_empty_prefix(self) -> None:
        await self.store.put("a.txt", b"")
        await self.store.put("b.txt", b"")

        keys = await self.source.process(store=self.store, prefix="")
        assert "a.txt" in keys
        assert "b.txt" in keys

    async def test_rejects_non_object_store(self) -> None:
        with self.assertRaises(TypeError) as ctx:
            await self.source.process(store=object(), prefix="")  # type: ignore[arg-type]
        assert "ObjectStore" in str(ctx.exception)

    async def test_rejects_non_string_prefix(self) -> None:
        with self.assertRaises(TypeError):
            await self.source.process(store=self.store, prefix=123)  # type: ignore[arg-type]


class TestObjectStoreKnot(unittest.IsolatedAsyncioTestCase):
    async def test_returns_store_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalFilesystemStore(LocalFilesystemConfig(root=Path(tmp)))
            knot = ObjectStoreKnot(store=store, _config=KnotConfig(id="store"))
            result = await knot.process(store=store)
            assert result is store
