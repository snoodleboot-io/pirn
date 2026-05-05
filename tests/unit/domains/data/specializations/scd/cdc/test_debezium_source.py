"""Tests for :class:`DebeziumSource`."""

from __future__ import annotations

import json
import unittest
from collections.abc import AsyncIterator
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.connectors.message_broker import MessageBroker
from pirn.domains.data.specializations.scd.cdc.debezium_source import (
    DebeziumSource,
)
from pirn.tapestry import Tapestry


class _StubRecord:
    """Trivial broker record exposing a ``value`` attribute."""

    def __init__(self, value: Any) -> None:
        self.value = value


class _StubBroker(MessageBroker):
    """In-memory broker fixture that yields a fixed sequence of records."""

    def __init__(self, records: list[Any]) -> None:
        self._records = list(records)

    async def publish(
        self, topic: str, value: bytes, *, key: bytes | None = None,
        headers: dict[str, bytes] | None = None,
    ) -> None:
        raise NotImplementedError("_StubBroker is consume-only")

    async def consume(self, topic: str, *, group: str | None = None) -> AsyncIterator[Any]:
        records = list(self._records)

        async def _generator() -> AsyncIterator[Any]:
            for record in records:
                yield record

        return _generator()


def _envelope(
    op: str,
    *,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    ts_ms: int = 1700000000000,
) -> dict[str, Any]:
    return {
        "op": op,
        "before": before,
        "after": after,
        "source": {"connector": "stub", "name": "test"},
        "ts_ms": ts_ms,
    }


class TestConstruction(unittest.TestCase):
    def test_rejects_non_broker(self) -> None:
        with self.assertRaisesRegex(TypeError, "MessageBroker"):
            DebeziumSource(
                broker="not-a-broker",  # type: ignore[arg-type]
                topic="t",
                _config=KnotConfig(id="cdc"),
            )

    def test_rejects_empty_topic(self) -> None:
        broker = _StubBroker(records=[])
        with self.assertRaisesRegex(ValueError, "topic"):
            DebeziumSource(
                broker=broker,
                topic="",
                _config=KnotConfig(id="cdc"),
            )

    def test_rejects_negative_max_messages(self) -> None:
        broker = _StubBroker(records=[])
        with self.assertRaisesRegex(ValueError, "max_messages"):
            DebeziumSource(
                broker=broker,
                topic="t",
                max_messages=-1,
                _config=KnotConfig(id="cdc"),
            )


class TestDebeziumSourceBehaviour(unittest.IsolatedAsyncioTestCase):
    async def test_emits_parsed_events(self) -> None:
        records = [
            _StubRecord(json.dumps(_envelope("c", after={"id": 1, "name": "A"}))),
            _StubRecord(
                json.dumps(
                    _envelope(
                        "u",
                        before={"id": 1, "name": "A"},
                        after={"id": 1, "name": "B"},
                    )
                )
            ),
            _StubRecord(json.dumps(_envelope("d", before={"id": 1}))),
        ]
        broker = _StubBroker(records)
        with Tapestry() as t:
            DebeziumSource(
                broker=broker,
                topic="orders.public.customers",
                max_messages=3,
                _config=KnotConfig(id="cdc"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        events = next(iter(result.outputs.values()))
        assert len(events) == 3
        assert events[0]["op"] == "c"
        assert events[0]["after"] == {"id": 1, "name": "A"}
        assert events[0]["before"] is None
        assert events[1]["op"] == "u"
        assert events[1]["before"] == {"id": 1, "name": "A"}
        assert events[1]["after"] == {"id": 1, "name": "B"}
        assert events[2]["op"] == "d"
        assert events[2]["after"] is None

    async def test_accepts_dict_payload_directly(self) -> None:
        records = [
            _StubRecord(_envelope("c", after={"id": 9})),
        ]
        broker = _StubBroker(records)
        with Tapestry() as t:
            DebeziumSource(
                broker=broker,
                topic="t",
                max_messages=1,
                _config=KnotConfig(id="cdc"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        events = next(iter(result.outputs.values()))
        assert events[0]["op"] == "c"
        assert events[0]["after"] == {"id": 9}

    async def test_rejects_non_object_payload(self) -> None:
        records = [_StubRecord(json.dumps([1, 2, 3]))]
        broker = _StubBroker(records)
        with Tapestry() as t:
            DebeziumSource(
                broker=broker,
                topic="t",
                max_messages=1,
                _config=KnotConfig(id="cdc"),
            )
        result = await t.run(RunRequest())
        assert not result.succeeded

    async def test_rejects_envelope_missing_op(self) -> None:
        records = [_StubRecord(json.dumps({"after": {"id": 1}}))]
        broker = _StubBroker(records)
        with Tapestry() as t:
            DebeziumSource(
                broker=broker,
                topic="t",
                max_messages=1,
                _config=KnotConfig(id="cdc"),
            )
        result = await t.run(RunRequest())
        assert not result.succeeded

    async def test_rejects_unknown_op(self) -> None:
        records = [_StubRecord(json.dumps(_envelope("x")))]
        broker = _StubBroker(records)
        with Tapestry() as t:
            DebeziumSource(
                broker=broker,
                topic="t",
                max_messages=1,
                _config=KnotConfig(id="cdc"),
            )
        result = await t.run(RunRequest())
        assert not result.succeeded

    async def test_rejects_invalid_json(self) -> None:
        records = [_StubRecord("{not json")]
        broker = _StubBroker(records)
        with Tapestry() as t:
            DebeziumSource(
                broker=broker,
                topic="t",
                max_messages=1,
                _config=KnotConfig(id="cdc"),
            )
        result = await t.run(RunRequest())
        assert not result.succeeded

    async def test_max_messages_bounds_loop(self) -> None:
        # Ten valid records but max_messages=3.
        records = [
            _StubRecord(json.dumps(_envelope("c", after={"id": i})))
            for i in range(10)
        ]
        broker = _StubBroker(records)
        with Tapestry() as t:
            DebeziumSource(
                broker=broker,
                topic="t",
                max_messages=3,
                _config=KnotConfig(id="cdc"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        events = next(iter(result.outputs.values()))
        assert len(events) == 3
