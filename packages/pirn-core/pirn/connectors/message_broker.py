"""Interface for async streaming brokers (Kafka, Kinesis, PubSub, RabbitMQ,
Valkey Streams, Azure Service Bus).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue
from pirn.exceptions.connector_closed_error import ConnectorClosedError
from pirn.exceptions.connector_config_error import ConnectorConfigError


class MessageBroker(PirnOpaqueValue):
    """Interface every connector broker implementation must satisfy.

    Implementations:
      - :class:`pirn.connectors.streaming.kafka_broker.KafkaBroker`
      - :class:`pirn.connectors.streaming.valkey_stream_broker.ValkeyStreamBroker`

    Pydantic treats brokers as opaque (see
    :class:`pirn.core.pirn_opaque_value.PirnOpaqueValue`); the default
    identity-keyed serialiser keeps content-addressing cache stable
    without descending into live engine state.
    """

    async def publish(
        self,
        topic: str,
        value: bytes,
        *,
        key: bytes | None = None,
        headers: dict[str, bytes] | None = None,
    ) -> None:
        """Publish ``value`` to ``topic``."""
        raise NotImplementedError(f"{type(self).__name__} must implement publish()")

    async def consume(self, topic: str, *, group: str | None = None) -> AsyncIterator[Any]:
        """Yield consumed messages from ``topic``.

        Each yielded item exposes at least ``value``, ``key``, and
        ``headers`` attributes.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement consume()")

    @staticmethod
    def _closed_error(class_name: str) -> ConnectorClosedError:
        """Build the typed error for "used after close" — call sites ``raise`` it.

        Mirrors
        :meth:`pirn.connectors.connector_base.ConnectorBase._closed_error`
        for the ``MessageBroker`` hierarchy, which does not share
        ``ConnectorBase``.
        """
        return ConnectorClosedError(f"{class_name} is closed")

    @staticmethod
    def _missing_config_error(class_name: str, resource: str) -> ConnectorConfigError:
        """Build the typed error for "no config and no injected *resource*".

        Mirrors
        :meth:`pirn.connectors.connector_base.ConnectorBase._missing_config_error`
        for the ``MessageBroker`` hierarchy.
        """
        return ConnectorConfigError(f"{class_name}: missing config and no injected {resource}")

    def _clear_credentials(self) -> None:
        """Drop the in-memory credential reference held by the broker.

        Concrete brokers should call this from ``close()`` after tearing
        down the live producer/consumer. It nulls ``self._config`` so
        any credential strings (SASL passwords, AWS keys, connection
        strings) become garbage-collectable as soon as the caller drops
        the broker reference.
        """
        self._config = None
