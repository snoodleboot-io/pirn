"""Tests for :class:`ObjectStoreKnot` calling process() directly."""

from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.knots.object_store_knot import ObjectStoreKnot
from pirn.domains.connectors.object_storage.local_filesystem_config import LocalFilesystemConfig
from pirn.domains.connectors.object_storage.local_filesystem_store import LocalFilesystemStore


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
