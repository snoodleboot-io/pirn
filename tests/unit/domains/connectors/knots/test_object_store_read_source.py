"""Tests for :class:`ObjectStoreReadSource` — verifies it composes inside a
real :class:`Tapestry` and surfaces the backend's bytes through the
pipeline contract.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.connectors.knots.object_store_read_source import ObjectStoreReadSource
from pirn.domains.connectors.object_storage.local_filesystem_config import (
    LocalFilesystemConfig,
)
from pirn.domains.connectors.object_storage.local_filesystem_store import (
    LocalFilesystemStore,
)
from pirn.tapestry import Tapestry


class TestObjectStoreReadSource(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        tmp_path = Path(self._tmp.name)
        self.store = LocalFilesystemStore(LocalFilesystemConfig(root=tmp_path))

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_construct_rejects_non_object_store(self) -> None:
        with self.assertRaisesRegex(TypeError, "ObjectStore"):
            ObjectStoreReadSource(
                store=object(),  # type: ignore[arg-type]
                key="x",
                _config=KnotConfig(id="read"),
            )

    def test_construct_rejects_empty_key(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-empty"):
            ObjectStoreReadSource(
                store=self.store, key="", _config=KnotConfig(id="read")
            )

    async def test_runs_inside_tapestry_and_returns_bytes(self) -> None:
        await self.store.put("greeting.txt", b"hello, pirn")

        with Tapestry() as t:
            ObjectStoreReadSource(
                store=self.store,
                key="greeting.txt",
                _config=KnotConfig(id="read"),
            )

        result = await t.run(RunRequest())
        assert result.succeeded
        assert result.outputs["read"] == b"hello, pirn"

    async def test_streams_large_file_through_tapestry(self) -> None:
        _td = tempfile.TemporaryDirectory()
        self.addCleanup(_td.cleanup)
        store = LocalFilesystemStore(LocalFilesystemConfig(root=Path(_td.name), chunk_size=64))
        payload = b"x" * 4096
        await store.put("big.bin", payload)

        with Tapestry() as t:
            ObjectStoreReadSource(
                store=store, key="big.bin", _config=KnotConfig(id="big")
            )

        result = await t.run(RunRequest())
        assert result.outputs["big"] == payload
