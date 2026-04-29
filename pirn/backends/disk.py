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

from pirn.backends._signing import sign as _sign
from pirn.backends._signing import verify as _verify
from pirn.backends.base.data_store import DataStore

_PICKLE_PROTOCOL = 5


def _disk_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _disk_read(path: Path, content_hash: str) -> bytes:
    if not path.exists():
        raise KeyError(content_hash)
    return path.read_bytes()


def _disk_unlink(path: Path) -> None:
    if path.exists():
        path.unlink()


class LocalDiskDataStore(DataStore):
    """``DataStore`` backed by a directory tree on local disk.

    Pickle is used because we control both writers and readers; users
    who want JSON-only blobs can subclass and override ``_serialize`` /
    ``_deserialize``.

    All operations run in the default executor (``asyncio.to_thread``)
    so the calling event loop isn't blocked on disk IO.
    """

    def __init__(self, root: str | Path, *, signing_key: bytes | None = None) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)
        self._signing_key = signing_key

    def _path(self, content_hash: str) -> Path:
        # Strip the "sha256:" prefix for cleaner paths.
        clean = content_hash.removeprefix("sha256:")
        # Shard by 2-char prefix so we don't get millions of files in
        # one directory.
        prefix = clean[:2] if len(clean) >= 2 else "_"
        return self._root / prefix / f"{clean}.pkl"

    def _serialize(self, value: Any) -> bytes:
        payload = pickle.dumps(value, protocol=_PICKLE_PROTOCOL)
        if self._signing_key is not None:
            payload = _sign(payload, self._signing_key)
        return payload

    def _deserialize(self, payload: bytes) -> Any:
        if self._signing_key is not None:
            payload = _verify(payload, self._signing_key)
        return pickle.loads(payload)

    async def put(self, content_hash: str, value: Any) -> None:
        path = self._path(content_hash)
        payload = self._serialize(value)
        await asyncio.to_thread(_disk_write, path, payload)

    async def get(self, content_hash: str) -> Any:
        path = self._path(content_hash)
        payload = await asyncio.to_thread(_disk_read, path, content_hash)
        return self._deserialize(payload)

    async def has(self, content_hash: str) -> bool:
        path = self._path(content_hash)
        return await asyncio.to_thread(path.exists)

    async def scrub(self, content_hash: str) -> None:
        path = self._path(content_hash)
        await asyncio.to_thread(_disk_unlink, path)
