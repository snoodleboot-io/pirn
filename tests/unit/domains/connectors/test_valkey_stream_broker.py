"""Unit tests for :class:`ValkeyStreamBroker` using a stub client."""

from __future__ import annotations

from typing import Any

import pytest

from pirn.domains.connectors.message_broker import MessageBroker
from pirn.domains.connectors.streaming.valkey_stream_broker import ValkeyStreamBroker
from pirn.domains.connectors.streaming.valkey_stream_config import ValkeyStreamConfig


# ──────────────────────────────────────────────────────────── stub client


class StubValkey:
    """Mirrors the slice of valkey async client surface we depend on."""

    def __init__(self) -> None:
        # stream -> list of (id, fields)
        self.streams: dict[str, list[tuple[bytes, dict[bytes, bytes]]]] = {}
        # stream -> set[group]
        self.groups: dict[str, set[str]] = {}
        # acked: list of (stream, group, id)
        self.acked: list[tuple[str, str, bytes]] = []
        self.closed = False
        # Track which entries have been delivered per group.
        self._delivered: dict[tuple[str, str], int] = {}

    async def xadd(
        self, stream: str, fields: dict[bytes, bytes], *, maxlen: int | None = None
    ) -> bytes:
        self.streams.setdefault(stream, [])
        entry_id = f"0-{len(self.streams[stream]) + 1}".encode()
        self.streams[stream].append((entry_id, fields))
        return entry_id

    async def xgroup_create(
        self, stream: str, group: str, *, mkstream: bool = True
    ) -> str:
        if stream in self.groups and group in self.groups[stream]:
            raise Exception("BUSYGROUP Consumer Group name already exists")
        self.groups.setdefault(stream, set()).add(group)
        if stream not in self.streams and mkstream:
            self.streams[stream] = []
        return "OK"

    async def xreadgroup(
        self,
        group: str,
        consumer: str,
        streams: dict[str, str],
        *,
        count: int,
        block: int,
    ) -> list[tuple[str, list[tuple[bytes, dict[bytes, bytes]]]]]:
        # Return all undelivered entries for the first stream argument.
        out: list[tuple[str, list[tuple[bytes, dict[bytes, bytes]]]]] = []
        for stream in streams:
            entries = self.streams.get(stream, [])
            seen = self._delivered.get((stream, group), 0)
            new_entries = entries[seen : seen + count]
            if not new_entries:
                continue
            self._delivered[(stream, group)] = seen + len(new_entries)
            out.append((stream, new_entries))
        return out

    async def xack(self, stream: str, group: str, *ids: bytes) -> int:
        for i in ids:
            self.acked.append((stream, group, i))
        return len(ids)

    async def close(self) -> None:
        self.closed = True


# ────────────────────────────────────────────────────────── conformance


def test_implements_message_broker() -> None:
    broker = ValkeyStreamBroker(ValkeyStreamConfig(), client=StubValkey())
    assert isinstance(broker, MessageBroker)


# ────────────────────────────────────────────────────────────── publish


@pytest.mark.asyncio
class TestPublish:
    async def test_publish_writes_value_to_stream(self) -> None:
        stub = StubValkey()
        broker = ValkeyStreamBroker(ValkeyStreamConfig(), client=stub)
        await broker.publish("events", b"hello")
        assert stub.streams["events"][0][1] == {b"v": b"hello"}

    async def test_publish_with_key_and_headers(self) -> None:
        stub = StubValkey()
        broker = ValkeyStreamBroker(ValkeyStreamConfig(), client=stub)
        await broker.publish(
            "events", b"hello", key=b"user-1", headers={"trace": b"abc"}
        )
        fields = stub.streams["events"][0][1]
        assert fields[b"v"] == b"hello"
        assert fields[b"k"] == b"user-1"
        assert fields[b"h:trace"] == b"abc"

    async def test_rejects_non_bytes_value(self) -> None:
        broker = ValkeyStreamBroker(ValkeyStreamConfig(), client=StubValkey())
        with pytest.raises(TypeError, match="value must be bytes"):
            await broker.publish("t", "string")  # type: ignore[arg-type]


# ────────────────────────────────────────────────────────────── consume


@pytest.mark.asyncio
class TestConsume:
    async def test_consume_yields_records_with_value_and_key(self) -> None:
        stub = StubValkey()
        broker = ValkeyStreamBroker(
            ValkeyStreamConfig(consumer_group="g1"), client=stub
        )
        await broker.publish("events", b"a", key=b"k1")
        await broker.publish("events", b"b", key=b"k2")

        out: list[tuple[bytes, bytes | None]] = []
        async for rec in await broker.consume("events"):
            out.append((rec.value, rec.key))
        assert out == [(b"a", b"k1"), (b"b", b"k2")]

    async def test_consume_acknowledges_after_yield(self) -> None:
        stub = StubValkey()
        broker = ValkeyStreamBroker(
            ValkeyStreamConfig(consumer_group="g1"), client=stub
        )
        await broker.publish("events", b"a")
        async for _ in await broker.consume("events"):
            pass
        assert len(stub.acked) == 1
        assert stub.acked[0][0] == "events"
        assert stub.acked[0][1] == "g1"

    async def test_consume_requires_group(self) -> None:
        broker = ValkeyStreamBroker(ValkeyStreamConfig(), client=StubValkey())
        with pytest.raises(ValueError, match="group is required"):
            async for _ in await broker.consume("t"):
                pass

    async def test_consume_handles_existing_group(self) -> None:
        stub = StubValkey()
        broker = ValkeyStreamBroker(
            ValkeyStreamConfig(consumer_group="g1"), client=stub
        )
        # Pre-create the group so the broker hits the BUSYGROUP path.
        await stub.xgroup_create("events", "g1")
        await broker.publish("events", b"x")
        out: list[bytes] = []
        async for rec in await broker.consume("events"):
            out.append(rec.value)
        assert out == [b"x"]


# ────────────────────────────────────────────────────────────── headers


@pytest.mark.asyncio
class TestHeadersRoundTrip:
    async def test_headers_round_trip(self) -> None:
        stub = StubValkey()
        broker = ValkeyStreamBroker(
            ValkeyStreamConfig(consumer_group="g"), client=stub
        )
        await broker.publish(
            "t", b"v", headers={"a": b"1", "b": b"2"}
        )
        async for rec in await broker.consume("t"):
            assert rec.headers == {"a": b"1", "b": b"2"}


# ───────────────────────────────────────────────────────────── lifecycle


@pytest.mark.asyncio
class TestLifecycle:
    async def test_close_marks_closed(self) -> None:
        stub = StubValkey()
        broker = ValkeyStreamBroker(ValkeyStreamConfig(), client=stub)
        await broker.publish("t", b"v")
        await broker.close()
        assert stub.closed is True

    async def test_publish_after_close_raises(self) -> None:
        broker = ValkeyStreamBroker(ValkeyStreamConfig(), client=StubValkey())
        await broker.close()
        with pytest.raises(RuntimeError, match="closed"):
            await broker.publish("t", b"v")


# ───────────────────────────────────────────────────────── credential safety


class TestCredentialSafety:
    def test_repr_redacts_password(self) -> None:
        cfg = ValkeyStreamConfig(host="valkey", password="my-vk-pw")
        text = repr(cfg)
        assert "my-vk-pw" not in text
        assert "<redacted>" in text

    def test_audit_dict_redacts_password(self) -> None:
        cfg = ValkeyStreamConfig(password="leaks")
        d = cfg.to_audit_dict()
        assert d["password"] == "<redacted>"
