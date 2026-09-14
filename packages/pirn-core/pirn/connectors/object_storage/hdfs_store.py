"""HDFS :class:`ObjectStore` backed by WebHDFS REST or PyArrow HDFS bindings."""

from __future__ import annotations

import inspect
import logging
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import quote

from pirn.connectors.object_storage.hdfs_config import HDFSConfig
from pirn.connectors.object_storage.pyarrow_hdfs_client import PyarrowHdfsClient
from pirn.connectors.object_storage.web_hdfs_client import WebHdfsClient
from pirn.connectors.object_store import ObjectStore
from pirn.core.optional_dependency import OptionalDependency


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
                if inspect.isawaitable(result):
                    await result
            self._client = None
        self._closed = True
        self._logger.debug("hdfs.close")

    async def get(self, key: str) -> AsyncIterator[bytes]:
        self._validate_key(key)
        client = await self._ensure_client()
        path = self._full_path(key)
        chunk_size = self._config.chunk_size

        # design-decision-override: async-generator closure returned lazily; captures locals computed before iteration starts
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

        # design-decision-override: async-generator closure returned lazily; captures locals computed before iteration starts
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
            raise self._closed_error("HDFSStore")
        if self._client is not None:
            return self._client
        if self._config.use_webhdfs:
            return await self._create_webhdfs_client()
        return await self._create_pyarrow_client()

    async def _create_webhdfs_client(self) -> Any:
        requests = OptionalDependency.require("requests", extra="hdfs")
        config = self._config
        base_url = f"http://{config.namenode_host}:{config.namenode_port}/webhdfs/v1"
        user = quote(config.user or "hadoop", safe="")
        self._client = WebHdfsClient(base_url=base_url, user=user, session=requests.Session())
        self._logger.debug(
            "hdfs.webhdfs.connect",
            extra={"host": config.namenode_host, "port": config.namenode_port},
        )
        return self._client

    async def _create_pyarrow_client(self) -> Any:
        pafs = OptionalDependency.require("pyarrow.fs", extra="arrow")
        config = self._config
        fs = pafs.HadoopFileSystem(
            host=config.namenode_host,
            port=config.namenode_port,
            user=config.user or None,
        )
        self._client = PyarrowHdfsClient(fs=fs)
        self._logger.debug(
            "hdfs.pyarrow.connect",
            extra={"host": config.namenode_host},
        )
        return self._client
