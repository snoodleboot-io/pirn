"""``DebeziumSource`` — pirn :class:`Source` that yields parsed Debezium
change events from a message broker topic.

Debezium emits a uniform JSON envelope for every change event::

    {
      "op": "c" | "u" | "d" | "r",     # create, update, delete, snapshot read
      "before": {...},                  # row state before (NULL for insert)
      "after": {...},                   # row state after (NULL for delete)
      "source": {...},                  # connector / lsn / db metadata
      "ts_ms": 1234567890000
    }

This source consumes the topic and decodes each envelope into a plain
``Mapping[str, Any]`` of the same shape, with the keys ``op``, ``before``,
``after``, ``source`` and ``ts_ms`` always present. The caller is free to
feed the parsed events into any downstream Knot — e.g. a relational sink
(``CDCDebezium`` for a connector-applying target) or a queue.

The message broker connection is supplied via a :class:`CdcMessageBrokerKnot`
upstream, which wraps any concrete :class:`MessageBroker` implementation.

Validation:
    A non-Debezium-shaped message — one whose JSON payload is not a mapping
    or that lacks the ``op`` key — is rejected with :class:`ValueError`.
    Malformed envelopes cannot be recovered into a meaningful change event,
    and silently dropping them would hide a producer-side bug.

Source contract:
    :class:`Source` is one-shot, but Debezium streams are unbounded; the
    ``process()`` method requires a non-``None`` ``max_messages`` bound that
    breaks the consume loop after that many events are yielded. ``None``
    means "consume forever" and is only valid for direct ``_stream()`` calls
    in long-running streaming contexts.

Algorithm:
    1. Receive the resolved :class:`MessageBrokerConnection` wrapper, a topic
       string, and an optional ``max_messages`` bound.
    2. Validate that ``topic`` is a non-empty string.
    3. Validate that ``max_messages`` is ``None`` or a non-negative integer.
    4. Unwrap the broker via ``connection.client``.
    5. Consume up to ``max_messages`` records from the broker topic via
       ``_stream()``.
    6. Parse each record through :meth:`_parse_record`, normalising bytes,
       strings, and dicts into the canonical Debezium envelope dict.
    7. Return the list of parsed envelope dicts.

References:
    [1] Debezium — change event structure:
        https://debezium.io/documentation/reference/stable/connectors/postgresql.html#postgresql-change-events-value
    [2] Confluent — Kafka message schema for Debezium:
        https://www.confluent.io/blog/kafka-connect-deep-dive-converters-serialization-explained/
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Mapping
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.specializations.scd.cdc.cdc_message_broker_knot import (
    CdcMessageBrokerKnot,
)
from pirn.domains.data.specializations.scd.cdc.message_broker_connection import (
    MessageBrokerConnection,
)
from pirn.nodes.source import Source


class DebeziumSource(Source):
    """Async source that decodes Debezium-shaped messages into plain dicts."""

    _required_keys: ClassVar[tuple[str, ...]] = ("op",)
    _supported_ops: ClassVar[frozenset[str]] = frozenset({"c", "u", "d", "r"})

    def __init__(
        self,
        *,
        broker: CdcMessageBrokerKnot,
        topic: Knot | str,
        max_messages: Knot | int | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            broker=broker,
            topic=topic,
            max_messages=max_messages,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        *,
        broker: MessageBrokerConnection,
        topic: str,
        max_messages: int | None = None,
        **_: Any,
    ) -> list[Mapping[str, Any]]:
        """Consume up to max_messages Debezium events from the broker and return them.

        Args:
            broker: Resolved :class:`MessageBrokerConnection` wrapping the broker.
            topic: The broker topic to consume from.
            max_messages: Maximum number of events to consume. Must not be ``None``
                when called via ``process()``; use ``_stream()`` directly for
                unbounded streaming.

        Returns:
            A list of parsed Debezium envelope dicts, each with keys ``op``,
            ``before``, ``after``, ``source``, and ``ts_ms``.

        Raises:
            ValueError: If ``topic`` is empty or ``max_messages`` is negative.
            RuntimeError: If ``max_messages`` is ``None``.
        """
        if not isinstance(topic, str) or not topic:
            raise ValueError("DebeziumSource: topic must be a non-empty string")
        if max_messages is not None and (not isinstance(max_messages, int) or max_messages < 0):
            raise ValueError("DebeziumSource: max_messages must be None or a non-negative integer")
        if max_messages is None:
            raise RuntimeError(
                "DebeziumSource.process() requires max_messages — for "
                "unbounded streaming use _stream() directly"
            )
        events: list[Mapping[str, Any]] = []
        async for event in self._stream(broker=broker, topic=topic, max_messages=max_messages):
            events.append(event)
        return events

    async def _stream(
        self,
        *,
        broker: MessageBrokerConnection,
        topic: str,
        max_messages: int | None,
    ) -> AsyncIterator[Mapping[str, Any]]:
        consumed = 0
        async for record in await broker.client.consume(topic):
            event = self._parse_record(record)
            yield event
            consumed += 1
            if max_messages is not None and consumed >= max_messages:
                break

    def _parse_record(self, record: Any) -> Mapping[str, Any]:
        value = getattr(record, "value", record)
        if isinstance(value, (bytes, bytearray)):
            try:
                value = value.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValueError("DebeziumSource: message value is not valid UTF-8") from exc
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError as exc:
                raise ValueError("DebeziumSource: message value is not valid JSON") from exc
        if not isinstance(value, Mapping):
            raise ValueError("DebeziumSource: message value is not a JSON object")
        for required in self._required_keys:
            if required not in value:
                raise ValueError(f"DebeziumSource: envelope missing required key {required!r}")
        op = value.get("op")
        if op not in self._supported_ops:
            raise ValueError(f"DebeziumSource: unsupported op {op!r} in envelope")
        return {
            "op": op,
            "before": value.get("before"),
            "after": value.get("after"),
            "source": value.get("source"),
            "ts_ms": value.get("ts_ms"),
        }
