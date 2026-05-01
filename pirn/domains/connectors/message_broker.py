"""Interface for async streaming brokers (Kafka, Kinesis, PubSub, RabbitMQ,
Valkey Streams, Azure Service Bus).
"""

from __future__ import annotations

from typing import Any, AsyncIterator


class MessageBroker:
    """Interface every connector broker implementation must satisfy.

    Implementations:
      - :class:`pirn.domains.connectors.streaming.kafka_broker.KafkaBroker`
      - :class:`pirn.domains.connectors.streaming.valkey_stream_broker.ValkeyStreamBroker`
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
