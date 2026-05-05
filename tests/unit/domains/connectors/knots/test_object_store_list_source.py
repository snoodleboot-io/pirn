"""Tests for :class:`ObjectStoreListSource`."""

from __future__ import annotations

from pathlib import Path
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.connectors.knots.object_store_list_source import ObjectStoreListSource
from pirn.domains.connectors.object_storage.local_filesystem_config import (
    LocalFilesystemConfig,
)
from pirn.domains.connectors.object_storage.local_filesystem_store import (
    LocalFilesystemStore,
)
from pirn.tapestry import Tapestry



class _StandaloneTests(unittest.IsolatedAsyncioTestCase):
    async def test_lists_keys_under_prefix(self) -> None:
        import tempfile
        from pathlib import Path
        _td_test_lists_keys_under_prefix = tempfile.TemporaryDirectory()
        self.addCleanup(_td_test_lists_keys_under_prefix.cleanup)
        tmp_path = Path(_td_test_lists_keys_under_prefix.name)
        store = LocalFilesystemStore(LocalFilesystemConfig(root=tmp_path))
        await store.put("users/alice.json", b"{}")
        await store.put("users/bob.json", b"{}")
        await store.put("orders/1.json", b"{}")
    
        with Tapestry() as t:
            ObjectStoreListSource(
                store=store,
                prefix="users/",
                _config=KnotConfig(id="list"),
            )
    
        result = await t.run(RunRequest())
        assert result.succeeded
        assert result.outputs["list"] == [
            "users/alice.json",
            "users/bob.json",
        ]
    
    
    def test_construct_rejects_non_object_store(self) -> None:
        with self.assertRaisesRegex(TypeError, "ObjectStore"):
            ObjectStoreListSource(
                store=object(),  # type: ignore[arg-type]
                prefix="",
                _config=KnotConfig(id="list"),
            )
