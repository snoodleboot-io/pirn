"""``LocalBlobStore`` — a zero-dependency local-filesystem blob backend (F16-S4).

Stores objects as files under an injected root directory, root-scoped exactly
like the F6 filesystem tools: every key is resolved through
:func:`~pirn_agents.tools.filesystem._path_guard.resolve_in_root`, so absolute
paths, ``..`` traversal, and symlink escapes are refused. Reads and writes stream
chunk-by-chunk on a worker thread so a whole object is never held in memory and
the event loop is never blocked. Needs no optional extra.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Sequence
from pathlib import Path

from pirn_agents.connectors.blob_store import BlobStore
from pirn_agents.tools.filesystem._path_guard import resolve_in_root, resolve_root


class LocalBlobStore(BlobStore):
    """Root-scoped local-filesystem implementation of :class:`BlobStore`."""

    def __init__(self, *, root: str | Path, chunk_size: int = 65536) -> None:
        """Bind the store to a root directory and a streaming chunk size.

        Args:
            root: The directory every object is confined to.
            chunk_size: Number of bytes read/written per streamed chunk.

        Raises:
            ValueError: If ``root`` is not an existing directory or ``chunk_size``
                is not positive.
        """
        if chunk_size <= 0:
            raise ValueError(f"LocalBlobStore: chunk_size must be positive, got {chunk_size}")
        self._root = resolve_root(str(root))
        self._chunk_size = chunk_size

    async def get(self, key: str) -> AsyncIterator[bytes]:
        """Stream the object at ``key`` chunk-by-chunk.

        Raises:
            ValueError: If ``key`` escapes the root or is not a regular file.
        """
        resolved = resolve_in_root(self._root, key, must_exist=True)
        if not resolved.is_file():
            raise ValueError(f"LocalBlobStore: not a regular file: {key!r}")
        handle = await asyncio.to_thread(resolved.open, "rb")
        try:
            while True:
                chunk = await asyncio.to_thread(handle.read, self._chunk_size)
                if not chunk:
                    break
                yield chunk
        finally:
            await asyncio.to_thread(handle.close)

    async def put(self, key: str, data: AsyncIterator[bytes]) -> None:
        """Stream ``data`` into the object at ``key``, creating parent dirs.

        Raises:
            ValueError: If ``key`` is absolute, contains ``..``, or escapes the root.
        """
        rel = Path(key)
        if rel.is_absolute():
            raise ValueError(f"LocalBlobStore: refusing absolute key {key!r}")
        if ".." in rel.parts:
            raise ValueError(f"LocalBlobStore: refusing '..' traversal in {key!r}")
        await asyncio.to_thread((self._root / rel).parent.mkdir, parents=True, exist_ok=True)
        resolved = resolve_in_root(self._root, key, must_exist=False)
        handle = await asyncio.to_thread(resolved.open, "wb")
        try:
            async for chunk in data:
                await asyncio.to_thread(handle.write, chunk)
        finally:
            await asyncio.to_thread(handle.close)

    async def list(self, prefix: str = "") -> Sequence[str]:
        """Return the sorted POSIX keys under ``prefix`` (relative to the root)."""
        return await asyncio.to_thread(self._list_sync, prefix)

    def _list_sync(self, prefix: str) -> list[str]:
        """Walk the root and collect file keys matching ``prefix``."""
        keys: list[str] = []
        for path in self._root.rglob("*"):
            if path.is_file():
                key = path.relative_to(self._root).as_posix()
                if key.startswith(prefix):
                    keys.append(key)
        return sorted(keys)
