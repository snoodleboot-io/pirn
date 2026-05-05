"""``CDCDebezium`` — Change Data Capture sink that applies Debezium-shaped
envelopes from a :class:`MessageBroker` to a relational target table.

Debezium emits a uniform JSON envelope for every change event::

    {
      "op": "c" | "u" | "d" | "r",     # create, update, delete, snapshot read
      "before": {...},                  # row state before the change (NULL for insert)
      "after": {...},                   # row state after the change (NULL for delete)
      "source": {...},                  # connector / lsn / db metadata
      "ts_ms": 1234567890000
    }

This knot consumes the topic, decodes each envelope and applies
the change to ``target_table``:

* ``op="c"`` or ``op="r"`` — ``INSERT`` ``after``.
* ``op="u"`` — ``UPDATE`` non-key columns from ``after``, joining on
  ``key_columns`` from ``after`` (preferred) or ``before`` (fallback).
* ``op="d"`` — ``DELETE`` rows whose ``key_columns`` match ``before``.

Bounded vs unbounded
--------------------
``max_messages`` bounds the consume loop:

* ``None`` — consume forever (production stream).
* ``int`` — break after applying that many envelopes; convenient for
  tests and for batch-style apply jobs.

The knot returns a primitive summary so pirn's content-addressing hash
does not have to walk a :class:`RunResult`.

Algorithm:
    1. Receive resolved ``broker``, ``topic``, ``target_pool``,
       ``target_table``, ``key_columns``, and ``max_messages`` in
       ``process()``.
    2. Validate all inputs: broker type, pool type, non-empty strings,
       identifier safety, and max_messages range.
    3. Consume events from the broker topic in a bounded loop.
    4. For each event, decode the Debezium envelope and dispatch to the
       appropriate SQL operation (INSERT, UPDATE, DELETE).
    5. Return a summary dict with ``applied`` and ``errors`` counts.

References:
    [1] Debezium — Change Data Capture documentation:
        https://debezium.io/documentation/
    [2] pirn — DatabaseConnectionPool interface:
        pirn/domains/connectors/database_connection_pool.py
    [3] pirn — MessageBroker interface:
        pirn/domains/connectors/message_broker.py
    [4] pirn — IdentifierValidator (SQL injection guard):
        pirn/domains/data/identifier_validator.py
"""

from __future__ import annotations

import json
import logging
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.connectors.message_broker import MessageBroker
from pirn.domains.data.identifier_validator import IdentifierValidator

_logger = logging.getLogger(__name__)


class CDCDebezium(Knot):
    """Apply Debezium change events from a broker topic to a target table."""

    def __init__(
        self,
        *,
        broker: Knot | MessageBroker,
        topic: Knot | str,
        target_pool: Knot | DatabaseConnectionPool,
        target_table: Knot | str,
        key_columns: Knot | tuple[str, ...],
        max_messages: Knot | int | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            broker=broker,
            topic=topic,
            target_pool=target_pool,
            target_table=target_table,
            key_columns=key_columns,
            max_messages=max_messages,
            _config=_config,
            **kwargs,
        )

    @staticmethod
    def _decode_envelope(record: Any, topic: str) -> dict[str, Any] | None:
        value = getattr(record, "value", record)
        if isinstance(value, (bytes, bytearray)):
            try:
                value = value.decode("utf-8")
            except UnicodeDecodeError:
                _logger.warning(
                    "cdc.debezium.decode_failed topic=%s reason=non_utf8", topic
                )
                return None
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                _logger.warning(
                    "cdc.debezium.decode_failed topic=%s reason=invalid_json", topic
                )
                return None
        if not isinstance(value, dict):
            _logger.warning(
                "cdc.debezium.decode_failed topic=%s reason=not_object", topic
            )
            return None
        return value

    @staticmethod
    async def _apply_insert(
        after: dict[str, Any],
        target_pool: DatabaseConnectionPool,
        target_table: str,
    ) -> None:
        if not after:
            raise ValueError("CDCDebezium: insert envelope missing 'after' payload")
        for column in after:
            IdentifierValidator.validate_column("after column", column)
        columns = tuple(after.keys())
        placeholders = ", ".join(["?"] * len(columns))
        column_list = ", ".join(columns)
        query = f"INSERT INTO {target_table} ({column_list}) VALUES ({placeholders})"
        await target_pool.execute(query, tuple(after[c] for c in columns))

    @staticmethod
    async def _apply_update(
        after: dict[str, Any],
        key_source: dict[str, Any],
        key_columns: tuple[str, ...],
        target_pool: DatabaseConnectionPool,
        target_table: str,
    ) -> None:
        if not after:
            raise ValueError("CDCDebezium: update envelope missing 'after' payload")
        non_key_columns = tuple(c for c in after if c not in key_columns)
        if not non_key_columns:
            return
        for column in non_key_columns:
            IdentifierValidator.validate_column("after column", column)
        set_clause = ", ".join(f"{c} = ?" for c in non_key_columns)
        where_clause = " AND ".join(f"{c} = ?" for c in key_columns)
        key_values = tuple(key_source.get(k) for k in key_columns)
        non_key_values = tuple(after[c] for c in non_key_columns)
        query = f"UPDATE {target_table} SET {set_clause} WHERE {where_clause}"
        await target_pool.execute(query, non_key_values + key_values)

    @staticmethod
    async def _apply_delete(
        before: dict[str, Any],
        key_columns: tuple[str, ...],
        target_pool: DatabaseConnectionPool,
        target_table: str,
    ) -> None:
        if not before:
            raise ValueError("CDCDebezium: delete envelope missing 'before' payload")
        where_clause = " AND ".join(f"{c} = ?" for c in key_columns)
        key_values = tuple(before.get(k) for k in key_columns)
        query = f"DELETE FROM {target_table} WHERE {where_clause}"
        await target_pool.execute(query, key_values)

    @staticmethod
    async def _apply_envelope(
        envelope: dict[str, Any],
        key_columns: tuple[str, ...],
        target_pool: DatabaseConnectionPool,
        target_table: str,
    ) -> None:
        op = envelope.get("op")
        before = envelope.get("before") or {}
        after = envelope.get("after") or {}
        if op in ("c", "r"):
            await CDCDebezium._apply_insert(after, target_pool, target_table)
        elif op == "u":
            key_source = after if after else before
            await CDCDebezium._apply_update(
                after, key_source, key_columns, target_pool, target_table
            )
        elif op == "d":
            await CDCDebezium._apply_delete(before, key_columns, target_pool, target_table)
        else:
            raise ValueError(f"CDCDebezium: unsupported op {op!r} in envelope")

    async def process(
        self,
        *,
        broker: Any,
        topic: Any,
        target_pool: Any,
        target_table: Any,
        key_columns: Any,
        max_messages: Any = None,
        **_: Any,
    ) -> dict[str, Any]:
        if not isinstance(broker, MessageBroker):
            raise TypeError("CDCDebezium: broker must be a MessageBroker")
        if not isinstance(target_pool, DatabaseConnectionPool):
            raise TypeError("CDCDebezium: target_pool must be a DatabaseConnectionPool")
        if not isinstance(topic, str) or not topic:
            raise ValueError("CDCDebezium: topic must be a non-empty string")
        IdentifierValidator.validate_column("target_table", target_table)
        key_tuple = tuple(key_columns)
        IdentifierValidator.validate_columns("key_columns", key_tuple)
        if max_messages is not None:
            if not isinstance(max_messages, int) or max_messages < 0:
                raise ValueError(
                    "CDCDebezium: max_messages must be None or a non-negative integer"
                )
        applied = 0
        errors = 0
        consumed = 0
        async for record in await broker.consume(topic):
            envelope = CDCDebezium._decode_envelope(record, topic)
            if envelope is None:
                errors += 1
            else:
                try:
                    await CDCDebezium._apply_envelope(
                        envelope, key_tuple, target_pool, target_table
                    )
                    applied += 1
                except Exception:
                    _logger.exception(
                        "cdc.debezium.apply_failed table=%s", target_table
                    )
                    errors += 1
            consumed += 1
            if max_messages is not None and consumed >= max_messages:
                break
        return {
            "succeeded": errors == 0,
            "target_table": target_table,
            "applied": applied,
            "errors": errors,
        }
