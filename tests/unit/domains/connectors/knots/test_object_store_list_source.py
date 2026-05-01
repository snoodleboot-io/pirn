"""Tests for :class:`ObjectStoreListSource`."""

from __future__ import annotations

from pathlib import Path

import pytest

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


@pytest.mark.asyncio
async def test_lists_keys_under_prefix(tmp_path: Path) -> None:
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


def test_construct_rejects_non_object_store() -> None:
    with pytest.raises(TypeError, match="ObjectStore"):
        ObjectStoreListSource(
            store=object(),  # type: ignore[arg-type]
            prefix="",
            _config=KnotConfig(id="list"),
        )
