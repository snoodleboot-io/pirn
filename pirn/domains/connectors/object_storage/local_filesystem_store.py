"""Async local-filesystem :class:`ObjectStore` implementation."""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import AsyncIterator, BinaryIO

from pirn.domains.connectors.object_storage.local_filesystem_config import (
    LocalFilesystemConfig,
)
from pirn.domains.connectors.object_store import ObjectStore


class LocalFilesystemStore(ObjectStore):
    """Async object store rooted at a directory on the local filesystem.

    All keys are resolved through :meth:`_resolve_safe` which rejects paths
    that escape the configured root. Reads stream the file in
    ``chunk_size``-byte chunks so multi-GB files never land in memory.
    """

    def __init__(self, config: LocalFilesystemConfig) -> None:
        self._config = config
        self._root = config.root.resolve()
        self._logger = logging.getLogger(self.__class__.__module__)
        if config.create_root:
            self._root.mkdir(parents=True, exist_ok=True)
        elif not self._root.is_dir():
            raise FileNotFoundError(
                f"LocalFilesystemStore root does not exist: {self._root}"
            )

    @property
    def config(self) -> LocalFilesystemConfig:
        return self._config

    async def get(self, key: str) -> AsyncIterator[bytes]:
        path = self._resolve_safe(key)
        chunk_size = self._config.chunk_size
        f: BinaryIO = await asyncio.to_thread(open, path, "rb")

        async def _iter() -> AsyncIterator[bytes]:
            try:
                while True:
                    chunk = await asyncio.to_thread(f.read, chunk_size)
                    if not chunk:
                        break
                    yield chunk
            finally:
                await asyncio.to_thread(f.close)

        return _iter()

    async def put(self, key: str, body: AsyncIterator[bytes] | bytes) -> None:
        path = self._resolve_safe(key)
        await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
        f: BinaryIO = await asyncio.to_thread(open, path, "wb")
        try:
            if isinstance(body, (bytes, bytearray)):
                await asyncio.to_thread(f.write, bytes(body))
            else:
                async for chunk in body:
                    if not isinstance(chunk, (bytes, bytearray)):
                        raise TypeError(
                            "LocalFilesystemStore.put: body iterator must yield "
                            f"bytes; got {type(chunk).__name__}"
                        )
                    await asyncio.to_thread(f.write, bytes(chunk))
        finally:
            await asyncio.to_thread(f.close)
        self._logger.debug("local.put", extra={"key": key, "root": str(self._root)})

    async def delete(self, key: str) -> None:
        path = self._resolve_safe(key)
        try:
            await asyncio.to_thread(path.unlink)
        except FileNotFoundError:
            return
        self._logger.debug("local.delete", extra={"key": key})

    async def list(self, prefix: str = "") -> AsyncIterator[str]:
        if prefix:
            base = self._resolve_safe(
                prefix.rstrip("/") if prefix.endswith("/") else prefix
            )
        else:
            base = self._root

        async def _iter() -> AsyncIterator[str]:
            if not base.exists() or not base.is_dir():
                return
            for path in sorted(base.rglob("*")):
                if path.is_file():
                    yield str(path.relative_to(self._root))

        return _iter()

    def _resolve_safe(self, key: str) -> Path:
        """Resolve ``key`` against the root and reject escapes.

        Raises ``ValueError`` for empty / absolute / NUL-containing keys and
        ``PermissionError`` for keys that resolve outside the root.
        """
        if not key:
            raise ValueError("key must be a non-empty relative path")
        if "\x00" in key:
            raise ValueError("key contains NUL byte")
        if os.path.isabs(key):
            raise ValueError(f"key must be relative, got absolute: {key!r}")

        candidate = (self._root / key).resolve()
        try:
            candidate.relative_to(self._root)
        except ValueError as exc:
            # Surface the rejection without echoing the resolved path —
            # the caller-supplied key is enough context.
            raise PermissionError(
                f"key {key!r} resolves outside the configured root"
            ) from exc
        return candidate
