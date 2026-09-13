"""``_PyArrowHDFSClient`` — thin PyArrow HDFS adapter used by :class:`HDFSStore`."""

from __future__ import annotations

import asyncio
from typing import Any


class _PyArrowHDFSClient:
    """Thin PyArrow HDFS adapter."""

    def __init__(self, *, fs: Any) -> None:
        self._fs = fs

    async def get(self, path: str) -> bytes:
        return await asyncio.to_thread(self._sync_get, path)

    def _sync_get(self, path: str) -> bytes:
        with self._fs.open_input_stream(path) as f:
            return f.read()

    async def put(self, path: str, data: bytes) -> None:
        await asyncio.to_thread(self._sync_put, path, data)

    def _sync_put(self, path: str, data: bytes) -> None:
        with self._fs.open_output_stream(path) as f:
            f.write(data)

    async def delete(self, path: str) -> None:
        await asyncio.to_thread(self._fs.delete_file, path)

    async def list(self, path: str) -> list[str]:
        return await asyncio.to_thread(self._sync_list, path)

    def _sync_list(self, path: str) -> list[str]:
        file_info = self._fs.get_file_info(self._fs.FileSelector(path, recursive=False))
        return [fi.path for fi in file_info]
