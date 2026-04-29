"""Local disk ``DataStore``.

Values are cloudpickled and stored under
``{root}/{prefix}/{rest_of_hash}.pkl``.  The first 2 hex chars of the
hash form the prefix directory so a single hash directory doesn't
accumulate millions of entries on a busy run history.

Suitable for single-host deployments that want durable values across
runs.  Pair with ``SQLiteHistory`` or ``DuckDBHistory`` for the
matching lineage records.

MinIO note: MinIO is S3-compatible — use ``S3DataStore(endpoint_url=...)``
rather than this class for MinIO deployments.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from pirn.backends._signer import _Signer
from pirn.backends.base._cloud_object_store import _CloudObjectStore


class LocalDiskDataStore(_CloudObjectStore):
    """``DataStore`` backed by a directory tree on local disk.

    cloudpickle is used because we control both writers and readers and
    need to handle arbitrary Python objects including lambdas and closures.
    Users who want JSON-only blobs can subclass and override
    ``_serialize`` / ``_deserialize``.

    All IO runs in the default executor (``asyncio.to_thread``) so the
    calling event loop isn't blocked on disk IO.
    """

    def __init__(self, root: str | Path, *, signer: _Signer | None = None) -> None:
        super().__init__(signer=signer)
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)

    def _object_key(self, content_hash: str) -> str:
        clean = content_hash.removeprefix("sha256:")
        prefix = clean[:2] if len(clean) >= 2 else "_"
        return str(self._root / prefix / f"{clean}.pkl")

    async def _put_bytes(self, key: str, payload: bytes) -> None:
        await asyncio.to_thread(self.__write, Path(key), payload)

    async def _get_bytes(self, key: str) -> bytes:
        return await asyncio.to_thread(self.__read, Path(key), key)

    async def _has_key(self, key: str) -> bool:
        return await asyncio.to_thread(Path(key).exists)

    async def _delete_key(self, key: str) -> None:
        await asyncio.to_thread(self.__unlink, Path(key))

    def __write(self, path: Path, payload: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)

    def __read(self, path: Path, key: str) -> bytes:
        if not path.exists():
            raise KeyError(key)
        return path.read_bytes()

    def __unlink(self, path: Path) -> None:
        if path.exists():
            path.unlink()
