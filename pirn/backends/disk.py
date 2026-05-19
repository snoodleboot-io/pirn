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

    def __init__(
        self,
        root: str | Path,
        *,
        signer: _Signer | None = None,
        allow_unsigned: bool = False,
    ) -> None:
        """Initialise the store.

        Creates ``root`` (and all intermediate directories) if it does not
        already exist.

        Args:
            root: Root directory for the store.  All value files are written
                inside this tree.
            signer: An ``_Signer`` for HMAC payload signing.  Required unless
                ``allow_unsigned=True`` is set.
            allow_unsigned: If ``True``, the store operates without signing.
                Requires ``PIRN_ALLOW_UNSIGNED=1`` in the environment.

        Raises:
            ValueError: If signing is not configured correctly.
        """
        super().__init__(signer=signer, allow_unsigned=allow_unsigned)
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)

    def _object_key(self, content_hash: str) -> str:
        """Derive an absolute file path from a content hash.

        The first two hex chars of the hash form a prefix directory so that
        a busy store does not accumulate millions of entries in a single
        directory.  Path traversal is blocked by a ``is_relative_to`` check.

        Args:
            content_hash: SHA-256 hex digest, possibly prefixed with
                ``sha256:``.

        Returns:
            Absolute path string of the form
            ``{root}/{prefix}/{rest_of_hash}.pkl``.

        Raises:
            ValueError: If the resolved path escapes the store root
                (path traversal attempt).
        """
        clean = content_hash.removeprefix("sha256:")
        prefix = clean[:2] if len(clean) >= 2 else "_"
        resolved = (self._root / prefix / f"{clean}.pkl").resolve()
        if not resolved.is_relative_to(self._root.resolve()):
            raise ValueError(
                f"LocalDiskDataStore: content_hash {content_hash!r} resolves outside the store root"
            )
        return str(resolved)

    async def _put_bytes(self, key: str, payload: bytes) -> None:
        """Write raw bytes to a file, creating parent directories as needed.

        Args:
            key: Absolute file path returned by :meth:`_object_key`.
            payload: Bytes to write.
        """
        await asyncio.to_thread(self.__write, Path(key), payload)

    async def _get_bytes(self, key: str) -> bytes:
        """Read raw bytes from a file.

        Args:
            key: Absolute file path returned by :meth:`_object_key`.

        Returns:
            File contents as bytes.

        Raises:
            KeyError: If the file does not exist.
        """
        return await asyncio.to_thread(self.__read, Path(key), key)

    async def _has_key(self, key: str) -> bool:
        """Return ``True`` if the file at ``key`` exists.

        Args:
            key: Absolute file path returned by :meth:`_object_key`.

        Returns:
            ``True`` if the file exists, ``False`` otherwise.
        """
        return await asyncio.to_thread(Path(key).exists)

    async def _delete_key(self, key: str) -> None:
        """Delete the file at ``key`` if it exists; no-op otherwise.

        Args:
            key: Absolute file path returned by :meth:`_object_key`.
        """
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
