"""ATDD acceptance test: ``CDCDebezium`` end-to-end.

A stub :class:`MessageBroker` yields prebuilt Debezium envelopes (insert,
update, delete) and the CDC knot applies them to a SQLite target. The
test asserts the target's row state after each operation is consistent
with the stream of envelopes.
"""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.connectors.databases.sqlite_config import SqliteConfig
from pirn.domains.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.connectors.message_broker import MessageBroker
from pirn.domains.data.specializations.scd.cdc_debezium import CDCDebezium
from pirn.tapestry import Tapestry


class _StubRecord:
    """Bytes-only consumer record mirroring real broker records."""

    def __init__(self, value: bytes) -> None:
        self.value = value
        self.key: bytes | None = None
        self.headers: dict[str, bytes] = {}


class _StubBroker(MessageBroker):
    """Test broker that yields a bounded list of envelopes once consumed."""

    def __init__(self, envelopes: list[dict[str, Any]]) -> None:
        self._envelopes = envelopes

    async def publish(
        self,
        topic: str,
        value: bytes,
        *,
        key: bytes | None = None,
        headers: dict[str, bytes] | None = None,
    ) -> None:
        raise NotImplementedError("_StubBroker is consume-only")

    async def consume(
        self, topic: str, *, group: str | None = None
    ) -> AsyncIterator[Any]:
        envelopes = self._envelopes

        async def _iter() -> AsyncIterator[Any]:
            for envelope in envelopes:
                yield _StubRecord(json.dumps(envelope).encode("utf-8"))

        return _iter()


@pytest.fixture
async def target_pool() -> SqlitePool:
    pool = SqlitePool(SqliteConfig(database=":memory:"))
    await pool.execute(
        "CREATE TABLE replicated_orders ("
        "  id INTEGER PRIMARY KEY,"
        "  amount REAL NOT NULL,"
        "  region TEXT NOT NULL"
        ")"
    )
    yield pool
    await pool.close()


@pytest.mark.asyncio
async def test_cdc_debezium_applies_insert_update_delete(
    target_pool: SqlitePool,
) -> None:
    envelopes = [
        {"op": "c", "before": None, "after": {"id": 1, "amount": 10.0, "region": "EU"}},
        {"op": "c", "before": None, "after": {"id": 2, "amount": 20.0, "region": "US"}},
        {
            "op": "u",
            "before": {"id": 1, "amount": 10.0, "region": "EU"},
            "after": {"id": 1, "amount": 15.0, "region": "EU"},
        },
        {
            "op": "d",
            "before": {"id": 2, "amount": 20.0, "region": "US"},
            "after": None,
        },
    ]
    broker = _StubBroker(envelopes)

    with Tapestry() as t:
        CDCDebezium(
            broker=broker,
            topic="cdc.orders",
            target_pool=target_pool,
            target_table="replicated_orders",
            key_columns=("id",),
            max_messages=len(envelopes),
            _config=KnotConfig(id="cdc"),
        )
    result = await t.run(RunRequest())
    assert result.succeeded, [(r.knot_id, r.outcome) for r in result.lineage]

    rows = await target_pool.fetch_all(
        "SELECT id, amount, region FROM replicated_orders ORDER BY id"
    )
    # id=1 inserted then updated to amount=15.0; id=2 inserted then deleted.
    assert rows == [(1, 15.0, "EU")]


@pytest.mark.asyncio
async def test_cdc_debezium_counts_errors_for_invalid_envelope(
    target_pool: SqlitePool,
) -> None:
    envelopes = [
        {"op": "c", "before": None, "after": {"id": 1, "amount": 10.0, "region": "EU"}},
        {"op": "z"},  # unknown op: counted as error
    ]
    broker = _StubBroker(envelopes)

    with Tapestry() as t:
        CDCDebezium(
            broker=broker,
            topic="cdc.orders",
            target_pool=target_pool,
            target_table="replicated_orders",
            key_columns=("id",),
            max_messages=len(envelopes),
            _config=KnotConfig(id="cdc"),
        )
    result = await t.run(RunRequest())
    # Outer Tapestry succeeded — the SubTapestry ran to completion and
    # reported the error count in its returned summary.
    assert result.succeeded
    payload = result.outputs["cdc"]
    assert payload["applied"] == 1
    assert payload["errors"] == 1
    assert payload["succeeded"] is False
