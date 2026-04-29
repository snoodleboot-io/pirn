"""Local disk ``DataStore``.

Values are pickled and stored under
``{root}/{prefix}/{rest_of_hash}.pkl``.  The first 2 hex chars of the
hash form the prefix directory so a single hash directory doesn't
accumulate millions of entries on a busy run history.

Suitable for single-host deployments that want durable values across
runs.  Pair with ``SQLiteHistory`` or ``DuckDBHistory`` for the
matching lineage records.
"""

from __future__ import annotations

import asyncio
import pickle
from pathlib import Path
from typing import Any


class LocalDiskDataStore:
    """``DataStore`` backed by a directory tree on local disk.

    Pickle is used because we control both writers and readers; users
    who want JSON-only blobs can subclass and override ``_serialize`` /
    ``_deserialize``.

    All operations run in the default executor (``asyncio.to_thread``)
    so the calling event loop isn't blocked on disk IO.
    """

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, content_hash: str) -> Path:
        # Strip the "sha256:" prefix for cleaner paths.
        clean = content_hash.removeprefix("sha256:")
        # Shard by 2-char prefix so we don't get millions of files in
        # one directory.
        prefix = clean[:2] if len(clean) >= 2 else "_"
        return self._root / prefix / f"{clean}.pkl"

    def _serialize(self, value: Any) -> bytes:
        return pickle.dumps(value)

    def _deserialize(self, payload: bytes) -> Any:
        return pickle.loads(payload)

    async def put(self, content_hash: str, value: Any) -> None:
        path = self._path(content_hash)
        payload = self._serialize(value)

        def _write() -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)

        await asyncio.to_thread(_write)

    async def get(self, content_hash: str) -> Any:
        path = self._path(content_hash)

        def _read() -> bytes:
            if not path.exists():
                raise KeyError(content_hash)
            return path.read_bytes()

        payload = await asyncio.to_thread(_read)
        return self._deserialize(payload)

    async def has(self, content_hash: str) -> bool:
        path = self._path(content_hash)
        return await asyncio.to_thread(path.exists)

    async def scrub(self, content_hash: str) -> None:
        path = self._path(content_hash)

        def _unlink() -> None:
            if path.exists():
                path.unlink()

        await asyncio.to_thread(_unlink)
