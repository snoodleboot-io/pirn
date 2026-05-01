"""Interface for async streaming brokers (Kafka, Kinesis, PubSub, RabbitMQ,
Valkey Streams, Azure Service Bus).
"""

from __future__ import annotations

from typing import Any, AsyncIterator

from pirn.core.pirn_opaque_value import PirnOpaqueValue


class MessageBroker(PirnOpaqueValue):
    """Interface every connector broker implementation must satisfy.

    Implementations:
      - :class:`pirn.domains.connectors.streaming.kafka_broker.KafkaBroker`
      - :class:`pirn.domains.connectors.streaming.valkey_stream_broker.ValkeyStreamBroker`

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
        raise NotImplementedError(
            f"{type(self).__name__} must implement publish()"
        )

    async def consume(
        self, topic: str, *, group: str | None = None
    ) -> AsyncIterator[Any]:
        """Yield consumed messages from ``topic``.

        Each yielded item exposes at least ``value``, ``key``, and
        ``headers`` attributes.
        """
        raise NotImplementedError(
            f"{type(self).__name__} must implement consume()"
        )

