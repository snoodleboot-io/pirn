"""RabbitMQ :class:`MessageBroker` backed by :mod:`aio_pika`."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

from pirn.domains.connectors.message_broker import MessageBroker
from pirn.domains.connectors.streaming.rabbitmq_config import RabbitMQConfig
from pirn.domains.connectors.streaming.rabbitmq_plain_message import (
    RabbitMQPlainMessage,
)


class RabbitMQBroker(MessageBroker):
    """RabbitMQ broker using ``aio_pika.connect_robust``.

    Tests inject a stub ``connection=`` exposing ``channel()``; production
    code constructs a real aio_pika connection lazily on first use.
    Messages are published via the default exchange with ``routing_key=topic``
    so the topic name maps directly to a queue name.
    """

    def __init__(
        self,
        config: RabbitMQConfig,
        *,
        connection: Any | None = None,
    ) -> None:
        if not isinstance(config, RabbitMQConfig):
            raise TypeError(
                f"RabbitMQBroker.config must be RabbitMQConfig, got {type(config).__name__}"
            )
        self._config = config
        self._connection = connection
        self._channel: Any | None = None
        self._closed = False
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> RabbitMQConfig:
        return self._config

    async def close(self) -> None:
        if self._channel is not None and hasattr(self._channel, "close"):
            close_result = self._channel.close()
            if hasattr(close_result, "__await__"):
                await close_result
        if self._connection is not None and hasattr(self._connection, "close"):
            close_result = self._connection.close()
            if hasattr(close_result, "__await__"):
                await close_result
        self._channel = None
        self._connection = None
        self._clear_credentials()
        self._closed = True
        self._logger.debug("rabbitmq.close")

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
                f"RabbitMQBroker.publish: value must be bytes, got {type(value).__name__}"
            )
        if key is not None and not isinstance(key, (bytes, bytearray)):
            raise TypeError(
                f"RabbitMQBroker.publish: key must be bytes or None, got {type(key).__name__}"
            )
        if headers is not None:
            for header_name, header_value in headers.items():
                if not isinstance(header_value, (bytes, bytearray)):
                    raise TypeError(
                        f"RabbitMQBroker.publish: header {header_name!r} must be bytes, "
                        f"got {type(header_value).__name__}"
                    )
        channel = await self._ensure_channel()
        message = self._build_message(value, key=key, headers=headers)
        default_exchange = channel.default_exchange
        await default_exchange.publish(message, routing_key=topic)
        self._logger.debug("rabbitmq.publish", extra={"topic": topic, "size": len(value)})

    async def consume(
        self,
        topic: str,
        *,
        group: str | None = None,
    ) -> AsyncIterator[Any]:
        """Consume from the queue named ``topic``.

        ``group`` is ignored — RabbitMQ multiplexes consumers on a queue by
        connection, not by group name. Use distinct queue names if you need
        independent fan-out.
        """
        channel = await self._ensure_channel()
        queue = await channel.declare_queue(topic, durable=True)

        async def _iter() -> AsyncIterator[Any]:
            async with queue.iterator() as queue_iter:
                async for message in queue_iter:
                    async with message.process():
                        yield message

        return _iter()

    def _build_message(
        self,
        value: bytes,
        *,
        key: bytes | None,
        headers: dict[str, bytes] | None,
    ) -> Any:
        try:
            import aio_pika  # type: ignore[import-untyped]
        except ImportError:
            return RabbitMQPlainMessage(
                body=bytes(value),
                key=bytes(key) if key is not None else None,
                headers=dict(headers) if headers else None,
            )
        message_headers: dict[str, Any] = {}
        if headers:
            for header_name, header_value in headers.items():
                message_headers[header_name] = bytes(header_value)
        kwargs: dict[str, Any] = {"body": bytes(value)}
        if message_headers:
            kwargs["headers"] = message_headers
        if key is not None:
            kwargs["correlation_id"] = key.decode("utf-8")
        return aio_pika.Message(**kwargs)

    async def _ensure_channel(self) -> Any:
        if self._closed:
            raise RuntimeError("RabbitMQBroker is closed")
        if self._connection is None:
            self._connection = await self._build_connection()
        if self._channel is None:
            self._channel = await self._connection.channel()
        return self._channel

    async def _build_connection(self) -> Any:
        try:
            import aio_pika  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ImportError(
                "RabbitMQBroker requires aio-pika; install via `pip install pirn[rabbitmq]`"
            ) from exc
        connection = await aio_pika.connect_robust(
            host=self._config.host,
            port=self._config.port,
            login=self._config.user or "guest",
            password=self._config.password or "guest",
            virtualhost=self._config.vhost,
            ssl=self._config.ssl,
        )
        self._logger.debug("rabbitmq.connect")
        return connection
