"""``MessageBrokerPublishSink`` — a pirn :class:`Sink` that publishes its
parent's bytes payload to a configured topic on any :class:`MessageBroker`
backend.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.message_broker import MessageBroker
from pirn.nodes.sink import Sink


class MessageBrokerPublishSink(Sink):
    """Sink that publishes one message per pipeline run to a fixed topic."""

    def __init__(
        self,
        *,
        broker: MessageBroker,
        topic: str,
        value: Knot,
        _config: KnotConfig,
        key: bytes | None = None,
        headers: dict[str, bytes] | None = None,
        **kwargs: Any,
    ) -> None:
        if not isinstance(broker, MessageBroker):
            raise TypeError(
                f"MessageBrokerPublishSink: broker must be a MessageBroker, "
                f"got {type(broker).__name__}"
            )
        if not isinstance(topic, str) or not topic:
            raise ValueError("MessageBrokerPublishSink: topic must be a non-empty string")
        self._broker = broker
        self._topic = topic
        self._key = key
        self._headers = headers
        super().__init__(value=value, _config=_config, **kwargs)

    @property
    def broker(self) -> MessageBroker:
        return self._broker

    @property
    def topic(self) -> str:
        return self._topic

    async def process(self, value: bytes, **_: Any) -> None:
        if not isinstance(value, (bytes, bytearray)):
            raise TypeError(
                f"MessageBrokerPublishSink: value must be bytes, got {type(value).__name__}"
            )
        await self._broker.publish(
            self._topic,
            bytes(value),
            key=self._key,
            headers=self._headers,
        )
