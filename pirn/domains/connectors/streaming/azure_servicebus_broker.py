"""Azure Service Bus :class:`MessageBroker` backed by ``azure-servicebus``."""

from __future__ import annotations

import logging
from typing import Any, AsyncIterator

from pirn.domains.connectors.message_broker import MessageBroker
from pirn.domains.connectors.streaming.azure_servicebus_config import (
    AzureServiceBusConfig,
)
from pirn.domains.connectors.streaming.azure_servicebus_stub_message import (
    AzureServiceBusStubMessage,
)


class AzureServiceBusBroker(MessageBroker):
    """Azure Service Bus broker over the asynchronous Python SDK.

    Production code constructs an
    ``azure.servicebus.aio.ServiceBusClient.from_connection_string(...)``
    lazily on first use; tests inject a stub via ``client=``.
    """

    def __init__(
        self,
        config: AzureServiceBusConfig,
        *,
        client: Any | None = None,
    ) -> None:
        if not isinstance(config, AzureServiceBusConfig):
            raise TypeError(
                "AzureServiceBusBroker.config must be AzureServiceBusConfig, "
                f"got {type(config).__name__}"
            )
        if client is None and config.connection_string is None:
            raise ValueError(
                "AzureServiceBusBroker: either inject a client or set "
                "AzureServiceBusConfig.connection_string"
            )
        self._config = config
        self._client = client
        self._closed = False
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> AzureServiceBusConfig:
        return self._config

    async def close(self) -> None:
        if self._client is not None and hasattr(self._client, "close"):
            close_result = self._client.close()
            if hasattr(close_result, "__await__"):
                await close_result
        self._client = None
        self._closed = True
        self._logger.debug("azure_servicebus.close")

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
                f"AzureServiceBusBroker.publish: value must be bytes, got {type(value).__name__}"
            )
        if key is not None and not isinstance(key, (bytes, bytearray)):
            raise TypeError(
                f"AzureServiceBusBroker.publish: key must be bytes or None, got {type(key).__name__}"
            )
        if headers is not None:
            for header_name, header_value in headers.items():
                if not isinstance(header_value, (bytes, bytearray)):
                    raise TypeError(
                        f"AzureServiceBusBroker.publish: header {header_name!r} "
                        f"must be bytes, got {type(header_value).__name__}"
                    )
        client = await self._ensure_client()
        sender = client.get_queue_sender(queue_name=topic)
        message = self._build_message(value, key=key, headers=headers)
        if hasattr(sender, "__aenter__"):
            async with sender as active_sender:
                await active_sender.send_messages(message)
        else:
            await sender.send_messages(message)
            close = getattr(sender, "close", None)
            if close is not None:
                result = close()
                if hasattr(result, "__await__"):
                    await result
        self._logger.debug(
            "azure_servicebus.publish",
            extra={"queue": topic, "size": len(value)},
        )

    async def consume(
        self,
        topic: str,
        *,
        group: str | None = None,
    ) -> AsyncIterator[Any]:
        """Receive messages from the queue named ``topic``.

        ``group`` is ignored — Azure Service Bus uses subscriptions on
        topics rather than group names on queues.
        """
        client = await self._ensure_client()
        receiver = client.get_queue_receiver(queue_name=topic)

        async def _iter() -> AsyncIterator[Any]:
            if hasattr(receiver, "__aenter__"):
                async with receiver as active_receiver:
                    async for message in active_receiver:
                        yield message
                        complete = getattr(
                            active_receiver, "complete_message", None
                        )
                        if complete is not None:
                            result = complete(message)
                            if hasattr(result, "__await__"):
                                await result
            else:
                try:
                    async for message in receiver:
                        yield message
                        complete = getattr(receiver, "complete_message", None)
                        if complete is not None:
                            result = complete(message)
                            if hasattr(result, "__await__"):
                                await result
                finally:
                    close = getattr(receiver, "close", None)
                    if close is not None:
                        result = close()
                        if hasattr(result, "__await__"):
                            await result

        return _iter()

    def _build_message(
        self,
        value: bytes,
        *,
        key: bytes | None,
        headers: dict[str, bytes] | None,
    ) -> Any:
        try:
            from azure.servicebus import (  # type: ignore[import-untyped]
                ServiceBusMessage,
            )
        except ImportError:
            return AzureServiceBusStubMessage(
                body=bytes(value),
                key=bytes(key) if key is not None else None,
                headers=dict(headers) if headers else None,
            )
        message_kwargs: dict[str, Any] = {"body": bytes(value)}
        if key is not None:
            message_kwargs["session_id"] = key.decode("utf-8")
        message = ServiceBusMessage(**message_kwargs)
        if headers:
            properties = getattr(message, "application_properties", None)
            if properties is None:
                message.application_properties = {
                    name: bytes(val) for name, val in headers.items()
                }
            else:
                for name, val in headers.items():
                    properties[name] = bytes(val)
        return message

    async def _ensure_client(self) -> Any:
        if self._closed:
            raise RuntimeError("AzureServiceBusBroker is closed")
        if self._client is None:
            self._client = await self._build_client()
        return self._client

    async def _build_client(self) -> Any:
        try:
            from azure.servicebus.aio import (  # type: ignore[import-untyped]
                ServiceBusClient,
            )
        except ImportError as exc:
            raise ImportError(
                "AzureServiceBusBroker requires azure-servicebus; install via "
                "`pip install pirn[azure-servicebus]`"
            ) from exc
        if self._config.connection_string is None:
            raise ValueError(
                "AzureServiceBusBroker: connection_string is required to "
                "construct a ServiceBusClient"
            )
        client = ServiceBusClient.from_connection_string(
            self._config.connection_string
        )
        self._logger.debug("azure_servicebus.connect")
        return client
