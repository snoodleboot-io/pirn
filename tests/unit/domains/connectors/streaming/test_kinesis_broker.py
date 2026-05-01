"""Unit tests for :class:`KinesisBroker` using a stub aioboto3 client."""

from __future__ import annotations

from typing import Any

import pytest

from pirn.domains.connectors.message_broker import MessageBroker
from pirn.domains.connectors.streaming.kinesis_broker import KinesisBroker
from pirn.domains.connectors.streaming.kinesis_config import KinesisConfig


# ──────────────────────────────────────────────────────────── stub client


class StubKinesis:
    """Mirrors the slice of the aioboto3 Kinesis client surface we depend on."""

    def __init__(
        self,
        *,
        records: list[dict[str, Any]] | None = None,
        shards: list[str] | None = None,
    ) -> None:
        self.put_records: list[dict[str, Any]] = []
        self._records = records or []
        self._shards = shards or ["shard-000"]
        self.closed = False

    async def put_record(
        self, *, StreamName: str, Data: bytes, PartitionKey: str
    ) -> dict[str, Any]:
        self.put_records.append(
            {"StreamName": StreamName, "Data": Data, "PartitionKey": PartitionKey}
        )
        return {"ShardId": self._shards[0], "SequenceNumber": "1"}

    async def describe_stream(self, *, StreamName: str) -> dict[str, Any]:
        return {
            "StreamDescription": {
                "Shards": [{"ShardId": shard_id} for shard_id in self._shards]
            }
        }

    async def get_shard_iterator(
        self,
        *,
        StreamName: str,
        ShardId: str,
        ShardIteratorType: str,
    ) -> dict[str, Any]:
        return {"ShardIterator": f"iter:{ShardId}"}

    async def get_records(self, *, ShardIterator: str) -> dict[str, Any]:
        records = self._records
        self._records = []
        return {"Records": records, "NextShardIterator": None if not records else "next"}

    async def close(self) -> None:
        self.closed = True


# ──────────────────────────────────────────────────────── construction


def test_implements_message_broker() -> None:
    broker = KinesisBroker(KinesisConfig(region="us-east-1"), client=StubKinesis())
    assert isinstance(broker, MessageBroker)


def test_rejects_non_config() -> None:
    with pytest.raises(TypeError, match="must be KinesisConfig"):
        KinesisBroker("not-a-config", client=StubKinesis())  # type: ignore[arg-type]


# ─────────────────────────────────────────────────────────────── publish


@pytest.mark.asyncio
class TestPublish:
    async def test_publish_bytes_value_uses_default_partition_key(self) -> None:
        stub = StubKinesis()
        broker = KinesisBroker(KinesisConfig(region="us-east-1"), client=stub)
        await broker.publish("events", b"hello")
        assert stub.put_records == [
            {"StreamName": "events", "Data": b"hello", "PartitionKey": "default"}
        ]

    async def test_publish_with_key_uses_partition_key(self) -> None:
        stub = StubKinesis()
        broker = KinesisBroker(KinesisConfig(region="us-east-1"), client=stub)
        await broker.publish("events", b"v", key=b"user-1")
        assert stub.put_records[0]["PartitionKey"] == "user-1"
        assert stub.put_records[0]["Data"] == b"v"

    async def test_rejects_non_bytes_value(self) -> None:
        broker = KinesisBroker(KinesisConfig(region="us-east-1"), client=StubKinesis())
        with pytest.raises(TypeError, match="value must be bytes"):
            await broker.publish("t", "string")  # type: ignore[arg-type]

    async def test_rejects_non_bytes_key(self) -> None:
        broker = KinesisBroker(KinesisConfig(region="us-east-1"), client=StubKinesis())
        with pytest.raises(TypeError, match="key must be bytes"):
            await broker.publish("t", b"v", key="not-bytes")  # type: ignore[arg-type]


# ─────────────────────────────────────────────────────────────── consume


@pytest.mark.asyncio
class TestConsume:
    async def test_yields_records_from_shard(self) -> None:
        stub = StubKinesis(
            records=[
                {"Data": b"a", "PartitionKey": "k1"},
                {"Data": b"b", "PartitionKey": "k2"},
            ]
        )
        broker = KinesisBroker(KinesisConfig(region="us-east-1"), client=stub)
        out: list[bytes] = []
        async for rec in await broker.consume("events"):
            out.append(rec["Data"])
        assert out == [b"a", b"b"]


# ───────────────────────────────────────────────────────────── lifecycle


@pytest.mark.asyncio
class TestLifecycle:
    async def test_close_is_idempotent(self) -> None:
        stub = StubKinesis()
        broker = KinesisBroker(KinesisConfig(region="us-east-1"), client=stub)
        await broker.publish("t", b"v")
        await broker.close()
        await broker.close()
        assert stub.closed is True

    async def test_publish_after_close_raises(self) -> None:
        broker = KinesisBroker(KinesisConfig(region="us-east-1"), client=StubKinesis())
        await broker.close()
        with pytest.raises(RuntimeError, match="closed"):
            await broker.publish("t", b"v")


# ───────────────────────────────────────────────────── credential safety


class TestCredentialSafety:
    def test_repr_redacts_credentials(self) -> None:
        cfg = KinesisConfig(
            region="us-east-1",
            access_key_id="AKIA-LEAKS",
            secret_access_key="hunter2",
            session_token="session-leak",
        )
        text = repr(cfg)
        assert "AKIA-LEAKS" not in text
        assert "hunter2" not in text
        assert "session-leak" not in text
        assert "<redacted>" in text

    def test_audit_dict_redacts_credentials(self) -> None:
        cfg = KinesisConfig(
            region="us-east-1",
            access_key_id="AKIA-LEAKS",
            secret_access_key="hunter2",
            session_token="session-leak",
        )
        d = cfg.to_audit_dict()
        assert d["access_key_id"] == "<redacted>"
        assert d["secret_access_key"] == "<redacted>"
        assert d["session_token"] == "<redacted>"
