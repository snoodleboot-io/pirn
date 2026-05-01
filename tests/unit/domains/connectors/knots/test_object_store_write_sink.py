"""Tests for :class:`ObjectStoreWriteSink` inside a real :class:`Tapestry`."""

from __future__ import annotations

from pathlib import Path

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.connectors.knots.object_store_write_sink import ObjectStoreWriteSink
from pirn.domains.connectors.object_storage.local_filesystem_config import (
    LocalFilesystemConfig,
)
from pirn.domains.connectors.object_storage.local_filesystem_store import (
    LocalFilesystemStore,
)
from pirn.tapestry import Tapestry


@knot
async def emit_payload() -> bytes:
    return b"persisted by pirn"


@pytest.mark.asyncio
async def test_writes_parents_bytes_to_store(tmp_path: Path) -> None:
    store = LocalFilesystemStore(LocalFilesystemConfig(root=tmp_path))

    with Tapestry() as t:
        payload = emit_payload(_config=KnotConfig(id="payload"))
        ObjectStoreWriteSink(
            store=store,
            key="out/result.bin",
            body=payload,
            _config=KnotConfig(id="sink"),
        )

    result = await t.run(RunRequest())
    assert result.succeeded
    # Verify the actual filesystem state.
    written = (tmp_path / "out" / "result.bin").read_bytes()
    assert written == b"persisted by pirn"


@pytest.mark.asyncio
async def test_rejects_non_bytes_body(tmp_path: Path) -> None:
    store = LocalFilesystemStore(LocalFilesystemConfig(root=tmp_path))

    @knot
    async def not_bytes() -> str:
        return "this is not bytes"

    with Tapestry() as t:
        text = not_bytes(_config=KnotConfig(id="text"))
        ObjectStoreWriteSink(
            store=store,
            key="x.bin",
            body=text,
            _config=KnotConfig(id="sink", validate_io=False),
        )

    result = await t.run(RunRequest())
    assert not result.succeeded
    assert any(
        "body must be bytes" in (exc.message or "") for exc in result.exceptions
    )


def test_construct_rejects_non_object_store() -> None:
    @knot
    async def emit() -> bytes:
        return b""

    with Tapestry():
        body = emit(_config=KnotConfig(id="emit"))
        with pytest.raises(TypeError, match="ObjectStore"):
            ObjectStoreWriteSink(
                store=object(),  # type: ignore[arg-type]
                key="x",
                body=body,
                _config=KnotConfig(id="sink"),
            )
