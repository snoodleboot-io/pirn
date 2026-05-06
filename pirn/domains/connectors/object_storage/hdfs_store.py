"""HDFS :class:`ObjectStore` backed by WebHDFS REST or PyArrow HDFS bindings."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

from pirn.domains.connectors.object_storage.hdfs_config import HDFSConfig
from pirn.domains.connectors.object_store import ObjectStore


class HDFSStore(ObjectStore):
    """Async object store against HDFS via WebHDFS REST API or PyArrow.

    Tests inject ``client=`` that exposes the same interface the store
    calls — ``get(path)``, ``put(path, data)``, ``delete(path)``,
    ``list(path)``. Production code constructs a real client lazily.
    """

    def __init__(
        self,
        config: HDFSConfig,
        *,
        client: Any | None = None,
    ) -> None:
        if not isinstance(config.namenode_host, str) or not config.namenode_host:
            raise ValueError("HDFSConfig.namenode_host is required")
        if not isinstance(config.namenode_port, int) or config.namenode_port <= 0:
            raise ValueError("HDFSConfig.namenode_port must be a positive integer")
        self._config = config
        self._client = client
        self._closed = False
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> HDFSConfig:
        return self._config

    async def close(self) -> None:
        if self._client is not None:
            close_fn = getattr(self._client, "close", None)
            if callable(close_fn):
                result = close_fn()
                if hasattr(result, "__await__"):
                    await result  # type: ignore[misc]
            self._client = None
        self._closed = True
        self._logger.debug("hdfs.close")

    async def get(self, key: str) -> AsyncIterator[bytes]:
        self._validate_key(key)
        client = await self._ensure_client()
        path = self._full_path(key)
        chunk_size = self._config.chunk_size

        async def _iter() -> AsyncIterator[bytes]:
            data = await client.get(path)
            offset = 0
            while offset < len(data):
                chunk = data[offset : offset + chunk_size]
                yield chunk
                offset += chunk_size

        return _iter()

    async def put(self, key: str, body: AsyncIterator[bytes] | bytes) -> None:
        self._validate_key(key)
        client = await self._ensure_client()
        path = self._full_path(key)
        if isinstance(body, (bytes, bytearray)):
            payload: bytes = bytes(body)
        else:
            chunks: list[bytes] = []
            async for chunk in body:
                if not isinstance(chunk, (bytes, bytearray)):
                    raise TypeError(
                        f"HDFSStore.put: body iterator must yield bytes; got {type(chunk).__name__}"
                    )
                chunks.append(bytes(chunk))
            payload = b"".join(chunks)
        await client.put(path, payload)
        self._logger.debug("hdfs.put", extra={"path": path, "size": len(payload)})

    async def delete(self, key: str) -> None:
        self._validate_key(key)
        client = await self._ensure_client()
        path = self._full_path(key)
        await client.delete(path)
        self._logger.debug("hdfs.delete", extra={"path": path})

    async def list(self, prefix: str = "") -> AsyncIterator[str]:
        client = await self._ensure_client()
        base = self._full_path(prefix) if prefix else self._config.base_path

        async def _iter() -> AsyncIterator[str]:
            entries = await client.list(base)
            for entry in sorted(entries):
                rel = entry[len(self._config.base_path) :].lstrip("/")
                if not prefix or rel.startswith(prefix):
                    yield rel

        return _iter()

    def _full_path(self, key: str) -> str:
        base = self._config.base_path.rstrip("/")
        return f"{base}/{key}"

    async def _ensure_client(self) -> Any:
        if self._closed:
            raise RuntimeError("HDFSStore is closed")
        if self._client is not None:
            return self._client
        if self._config.use_webhdfs:
            return await self._create_webhdfs_client()
        return await self._create_pyarrow_client()

    async def _create_webhdfs_client(self) -> Any:
        try:
            import requests  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ImportError(
                "HDFSStore (WebHDFS) requires requests; install via `pip install pirn[hdfs]`"
            ) from exc
        from urllib.parse import quote as _quote

        config = self._config
        scheme = "https" if getattr(config, "tls", False) else "http"
        base_url = f"{scheme}://{config.namenode_host}:{config.namenode_port}/webhdfs/v1"
        user = _quote(config.user or "hadoop", safe="")
        self._client = _WebHDFSClient(base_url=base_url, user=user, session=requests.Session())
        self._logger.debug(
            "hdfs.webhdfs.connect",
            extra={"host": config.namenode_host, "port": config.namenode_port},
        )
        return self._client

    async def _create_pyarrow_client(self) -> Any:
        try:
            import pyarrow.fs as pafs  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ImportError(
                "HDFSStore (PyArrow) requires pyarrow; install via `pip install pirn[hdfs-arrow]`"
            ) from exc
        config = self._config
        fs = pafs.HadoopFileSystem(  # type: ignore[attr-defined]
            host=config.namenode_host,
            port=config.namenode_port,
            user=config.user or None,
        )
        self._client = _PyArrowHDFSClient(fs=fs)
        self._logger.debug(
            "hdfs.pyarrow.connect",
            extra={"host": config.namenode_host},
        )
        return self._client


class _WebHDFSClient:
    """Thin synchronous WebHDFS adapter (runs in asyncio.to_thread in prod)."""

    def __init__(self, *, base_url: str, user: str, session: Any) -> None:
        self._base_url = base_url
        self._user = user
        self._session = session

    async def get(self, path: str) -> bytes:
        import asyncio

        return await asyncio.to_thread(self._sync_get, path)

    def _sync_get(self, path: str) -> bytes:
        url = f"{self._base_url}{path}?op=OPEN&user.name={self._user}"
        resp = self._session.get(url, allow_redirects=True)
        resp.raise_for_status()
        return resp.content

    async def put(self, path: str, data: bytes) -> None:
        import asyncio

        await asyncio.to_thread(self._sync_put, path, data)

    def _sync_put(self, path: str, data: bytes) -> None:
        url = f"{self._base_url}{path}?op=CREATE&overwrite=true&user.name={self._user}"
        resp = self._session.put(url, data=data, allow_redirects=True)
        resp.raise_for_status()

    async def delete(self, path: str) -> None:
        import asyncio

        await asyncio.to_thread(self._sync_delete, path)

    def _sync_delete(self, path: str) -> None:
        url = f"{self._base_url}{path}?op=DELETE&user.name={self._user}"
        resp = self._session.delete(url)
        resp.raise_for_status()

    async def list(self, path: str) -> list[str]:
        import asyncio

        return await asyncio.to_thread(self._sync_list, path)

    def _sync_list(self, path: str) -> list[str]:
        url = f"{self._base_url}{path}?op=LISTSTATUS&user.name={self._user}"
        resp = self._session.get(url)
        resp.raise_for_status()
        statuses = resp.json().get("FileStatuses", {}).get("FileStatus", [])
        return [f"{path.rstrip('/')}/{s['pathSuffix']}" for s in statuses if s.get("pathSuffix")]

    def close(self) -> None:
        self._session.close()


class _PyArrowHDFSClient:
    """Thin PyArrow HDFS adapter."""

    def __init__(self, *, fs: Any) -> None:
        self._fs = fs

    async def get(self, path: str) -> bytes:
        import asyncio

        return await asyncio.to_thread(self._sync_get, path)

    def _sync_get(self, path: str) -> bytes:
        with self._fs.open_input_stream(path) as f:
            return f.read()

    async def put(self, path: str, data: bytes) -> None:
        import asyncio

        await asyncio.to_thread(self._sync_put, path, data)

    def _sync_put(self, path: str, data: bytes) -> None:
        with self._fs.open_output_stream(path) as f:
            f.write(data)

    async def delete(self, path: str) -> None:
        import asyncio

        await asyncio.to_thread(self._fs.delete_file, path)

    async def list(self, path: str) -> list[str]:
        import asyncio

        return await asyncio.to_thread(self._sync_list, path)

    def _sync_list(self, path: str) -> list[str]:
        file_info = self._fs.get_file_info(self._fs.FileSelector(path, recursive=False))
        return [fi.path for fi in file_info]
