"""``MessageBrokerPublishSink`` — a pirn :class:`Sink` that publishes its
parent's bytes payload to a configured topic on any :class:`MessageBroker`
backend.

Algorithm:
    1. Validate that ``broker`` is a :class:`MessageBroker` and ``topic``
       is a non-empty string.
    2. Validate that ``value`` is ``bytes`` or ``bytearray``.
    3. Invoke ``await broker.publish(topic, bytes(value), key=key, headers=headers)``.


References:
    - :class:`pirn.domains.connectors.message_broker.MessageBroker`
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.message_broker import MessageBroker
from pirn.domains.connectors.knots.message_broker_knot import MessageBrokerKnot
from pirn.nodes.sink import Sink


class MessageBrokerPublishSink(Sink):
    """Sink that publishes one message per pipeline run to a fixed topic."""

    def __init__(
        self,
        *,
        broker: MessageBrokerKnot,
        topic: Knot | str,
        value: Knot,
        key: Knot | bytes | None = None,
        headers: Knot | dict | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(broker=broker, topic=topic, value=value, key=key, headers=headers, _config=_config, **kwargs)

    async def process(self, broker: MessageBroker, topic: str, value: bytes, key: bytes | None = None, headers: dict[str, bytes] | None = None, **_: Any) -> None:
        """Publish the bytes payload to the configured broker topic.

        Args:
            broker: The message broker to publish to.
            topic: The topic name to publish the message to.
            value: The bytes payload to publish to the broker.
            key: Optional message key bytes.
            headers: Optional message headers dict.

        Raises:
            TypeError: If broker is not a MessageBroker or value is not bytes.
            ValueError: If topic is empty.
        """
        if not isinstance(broker, MessageBroker):
            raise TypeError(
                f"MessageBrokerPublishSink: broker must be a MessageBroker, "
                f"got {type(broker).__name__}"
            )
        if not isinstance(topic, str) or not topic:
            raise ValueError("MessageBrokerPublishSink: topic must be a non-empty string")
        if not isinstance(value, (bytes, bytearray)):
            raise TypeError(
                f"MessageBrokerPublishSink: value must be bytes, got {type(value).__name__}"
            )
        await broker.publish(
            topic,
            bytes(value),
            key=key,
            headers=headers,
        )
