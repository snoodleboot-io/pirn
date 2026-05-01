"""Tests for :class:`ObjectStoreReadSource` — verifies it composes inside a
real :class:`Tapestry` and surfaces the backend's bytes through the
pipeline contract.
"""

from __future__ import annotations

from pathlib import Path

import pytest

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


@pytest.fixture
def populated_store(tmp_path: Path) -> LocalFilesystemStore:
    store = LocalFilesystemStore(LocalFilesystemConfig(root=tmp_path))
    return store


@pytest.mark.asyncio
async def test_construct_rejects_non_object_store() -> None:
    with pytest.raises(TypeError, match="ObjectStore"):
        ObjectStoreReadSource(
            store=object(),  # type: ignore[arg-type]
            key="x",
            _config=KnotConfig(id="read"),
        )


@pytest.mark.asyncio
async def test_construct_rejects_empty_key(
    populated_store: LocalFilesystemStore,
) -> None:
    with pytest.raises(ValueError, match="non-empty"):
        ObjectStoreReadSource(
            store=populated_store, key="", _config=KnotConfig(id="read")
        )


@pytest.mark.asyncio
async def test_runs_inside_tapestry_and_returns_bytes(
    populated_store: LocalFilesystemStore,
) -> None:
    await populated_store.put("greeting.txt", b"hello, pirn")

    with Tapestry() as t:
        ObjectStoreReadSource(
            store=populated_store,
            key="greeting.txt",
            _config=KnotConfig(id="read"),
        )

    result = await t.run(RunRequest())
    assert result.succeeded
    assert result.outputs["read"] == b"hello, pirn"


@pytest.mark.asyncio
async def test_streams_large_file_through_tapestry(
    tmp_path: Path,
) -> None:
    # Verify the tap-into-Tapestry path streams correctly for a sizeable
    # payload — exercises the chunk loop end-to-end.
    store = LocalFilesystemStore(LocalFilesystemConfig(root=tmp_path, chunk_size=64))
    payload = b"x" * 4096
    await store.put("big.bin", payload)

    with Tapestry() as t:
        ObjectStoreReadSource(
            store=store, key="big.bin", _config=KnotConfig(id="big")
        )

    result = await t.run(RunRequest())
    assert result.outputs["big"] == payload
