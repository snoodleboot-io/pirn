"""Valkey Streams :class:`MessageBroker` implementation."""

from __future__ import annotations

import logging
from typing import Any, AsyncIterator

from pirn.domains.connectors.message_broker import MessageBroker
from pirn.domains.connectors.streaming.valkey_record import ValkeyRecord
from pirn.domains.connectors.streaming.valkey_stream_config import ValkeyStreamConfig


class ValkeyStreamBroker(MessageBroker):
    """Async broker over Valkey ``XADD`` / ``XREADGROUP`` / ``XACK``."""

    def __init__(
        self,
        config: ValkeyStreamConfig,
        *,
        client: Any | None = None,
    ) -> None:
        self._config = config
        self._client = client
        self._closed = False
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> ValkeyStreamConfig:
        return self._config

    async def close(self) -> None:
        if self._client is not None and hasattr(self._client, "close"):
            close_result = self._client.close()
            if hasattr(close_result, "__await__"):
                await close_result
        self._client = None
        self._clear_credentials()
        self._closed = True
        self._logger.debug("valkey.close")

    async def publish(
        self,
        topic: str,
        value: bytes,
        *,
        key: bytes | None = None,
        headers: dict[str, bytes] | None = None,
    ) -> None:
        if not isinstance(value, (bytes, bytearray)):
            raise TypeError(
                f"ValkeyStreamBroker.publish: value must be bytes, got {type(value).__name__}"
            )
        client = await self._ensure_client()
        fields: dict[bytes, bytes] = {b"v": bytes(value)}
        if key is not None:
            fields[b"k"] = bytes(key)
        if headers:
            for header_name, header_value in headers.items():
                fields[b"h:" + header_name.encode("utf-8")] = bytes(header_value)
        await client.xadd(topic, fields)
        self._logger.debug("valkey.publish", extra={"stream": topic, "size": len(value)})

    async def consume(
        self,
        topic: str,
        *,
        group: str | None = None,
    ) -> AsyncIterator[Any]:
        client = await self._ensure_client()
        effective_group = group or self._config.consumer_group
        if effective_group is None:
            raise ValueError(
                "ValkeyStreamBroker.consume: group is required (pass group= "
                "or set consumer_group on the config)"
            )

        await self._ensure_group(client, topic, effective_group)

        async def _iter() -> AsyncIterator[Any]:
            while True:
                response = await client.xreadgroup(
                    effective_group,
                    self._config.consumer_name,
                    {topic: ">"},
                    count=self._config.count_per_read,
                    block=self._config.block_ms,
                )
                if not response:
                    return
                for _stream_name, entries in response:
                    for entry_id, fields in entries:
                        yield ValkeyRecord(
                            entry_id=entry_id, stream=topic, fields=fields
                        )
                        await client.xack(topic, effective_group, entry_id)

        return _iter()

    async def _ensure_client(self) -> Any:
        if self._closed:
            raise RuntimeError("ValkeyStreamBroker is closed")
        if self._client is None:
            self._client = await self._build_client()
        return self._client

    async def _build_client(self) -> Any:
        try:
            import valkey.asyncio as valkey_async  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ImportError(
                "ValkeyStreamBroker requires a valkey async client; install via "
                "`pip install pirn[valkey]`"
            ) from exc
        client = valkey_async.Valkey(  # type: ignore[attr-defined]
            host=self._config.host,
            port=self._config.port,
            password=self._config.password,
            ssl=self._config.use_tls,
        )
        self._logger.debug("valkey.connect")
        return client

    async def _ensure_group(
        self, client: Any, topic: str, group: str
    ) -> None:
        try:
            await client.xgroup_create(topic, group, mkstream=True)
        except Exception as exc:  # noqa: BLE001
            message = str(exc)
            if "BUSYGROUP" not in message and "already exists" not in message:
                raise
