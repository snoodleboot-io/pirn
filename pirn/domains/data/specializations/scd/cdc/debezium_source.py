"""``DebeziumSource`` — pirn :class:`Source` that yields parsed Debezium
change events from a :class:`MessageBroker` topic.

Debezium emits a uniform JSON envelope for every change event::

    {
      "op": "c" | "u" | "d" | "r",     # create, update, delete, snapshot read
      "before": {...},                  # row state before (NULL for insert)
      "after": {...},                   # row state after (NULL for delete)
      "source": {...},                  # connector / lsn / db metadata
      "ts_ms": 1234567890000
    }

This source consumes the topic and decodes each envelope into a
plain ``Mapping[str, Any]`` of the same shape, with the keys ``op``,
``before``, ``after``, ``source`` and ``ts_ms`` always present. The
caller is free to feed the parsed events into any downstream knot —
e.g. a relational sink (``CDCDebezium`` for a connector-applying
target) or a queue.

Validation
----------
A non-Debezium-shaped message — one whose JSON payload is not a
mapping or that lacks the ``op`` key — is rejected with
:class:`ValueError`. This is intentional: malformed envelopes cannot
be recovered into a meaningful change event, and silently dropping
them would hide a producer-side bug.

Source contract
---------------
:class:`Source` is one-shot, but Debezium streams are unbounded; the
constructor takes a ``max_messages`` bound that breaks the consume
loop after that many events are yielded. ``None`` (the default) means
"consume forever" — fine for a long-running streaming context, but
test fixtures should always pass a small integer.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Mapping
from typing import Any, ClassVar

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.message_broker import MessageBroker
from pirn.nodes.source import Source


class DebeziumSource(Source):
    """Async source that decodes Debezium-shaped messages into plain dicts."""

    _required_keys: ClassVar[tuple[str, ...]] = ("op",)
    _supported_ops: ClassVar[frozenset[str]] = frozenset({"c", "u", "d", "r"})

    def __init__(
        self,
        *,
        broker: MessageBroker,
        topic: str,
        max_messages: int | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(broker, MessageBroker):
            raise TypeError(
                "DebeziumSource: broker must be a MessageBroker"
            )
        if not isinstance(topic, str) or not topic:
            raise ValueError(
                "DebeziumSource: topic must be a non-empty string"
            )
        if max_messages is not None and (
            not isinstance(max_messages, int) or max_messages < 0
        ):
            raise ValueError(
                "DebeziumSource: max_messages must be None or a "
                "non-negative integer"
            )
        self._broker = broker
        self._topic = topic
        self._max_messages = max_messages
        super().__init__(_config=_config, **kwargs)

    @property
    def broker(self) -> MessageBroker:
        return self._broker

    @property
    def topic(self) -> str:
        return self._topic

    @property
    def max_messages(self) -> int | None:
        return self._max_messages

    async def process(self, **_: Any) -> list[Mapping[str, Any]]:
        """Consume up to max_messages Debezium events from the broker and return them as a list.

        Returns:
            A list of parsed Debezium envelope dicts, each with keys op,
            before, after, source, and ts_ms.

        Raises:
            RuntimeError: If max_messages is None, as unbounded streaming
            is not supported in process().
        """
        if self._max_messages is None:
            raise RuntimeError(
                "DebeziumSource.process() requires max_messages — for "
                "unbounded streaming use _stream() directly"
            )
        events: list[Mapping[str, Any]] = []
        async for event in self._stream():
            events.append(event)
        return events

    async def _stream(self) -> AsyncIterator[Mapping[str, Any]]:
        consumed = 0
        async for record in await self._broker.consume(self._topic):
            event = self._parse_record(record)
            yield event
            consumed += 1
            if (
                self._max_messages is not None
                and consumed >= self._max_messages
            ):
                break

    def _parse_record(self, record: Any) -> Mapping[str, Any]:
        value = getattr(record, "value", record)
        if isinstance(value, (bytes, bytearray)):
            try:
                value = value.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValueError(
                    "DebeziumSource: message value is not valid UTF-8"
                ) from exc
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    "DebeziumSource: message value is not valid JSON"
                ) from exc
        if not isinstance(value, Mapping):
            raise ValueError(
                "DebeziumSource: message value is not a JSON object"
            )
        for required in self._required_keys:
            if required not in value:
                raise ValueError(
                    f"DebeziumSource: envelope missing required key "
                    f"{required!r}"
                )
        op = value.get("op")
        if op not in self._supported_ops:
            raise ValueError(
                f"DebeziumSource: unsupported op {op!r} in envelope"
            )
        return {
            "op": op,
            "before": value.get("before"),
            "after": value.get("after"),
            "source": value.get("source"),
            "ts_ms": value.get("ts_ms"),
        }
