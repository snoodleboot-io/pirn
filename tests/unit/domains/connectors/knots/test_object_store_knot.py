"""Tests for :class:`ObjectStoreKnot` calling process() directly."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pirn.connectors.knots.object_store_knot import ObjectStoreKnot
from pirn.connectors.object_storage.local_filesystem_config import LocalFilesystemConfig
from pirn.connectors.object_storage.local_filesystem_store import LocalFilesystemStore
from pirn.core.knot_config import KnotConfig


class TestObjectStoreKnot(unittest.IsolatedAsyncioTestCase):
    async def test_returns_store_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalFilesystemStore(LocalFilesystemConfig(root=Path(tmp)))
            knot = ObjectStoreKnot(store=store, _config=KnotConfig(id="store"))
            result = await knot.process(store=store)
            assert result is store

    async def test_accepts_scalar_store_at_build_time(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalFilesystemStore(LocalFilesystemConfig(root=Path(tmp)))
            knot = ObjectStoreKnot(store=store, _config=KnotConfig(id="store"))
            result = await knot.process(store=store)
            assert isinstance(result, LocalFilesystemStore)
