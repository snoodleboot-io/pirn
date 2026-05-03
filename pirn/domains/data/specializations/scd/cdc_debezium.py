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

This SubTapestry consumes the topic, decodes each envelope and applies
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
"""

from __future__ import annotations

import json
import logging
from typing import Any, Sequence

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import (
    DatabaseConnectionPool,
)
from pirn.domains.connectors.message_broker import MessageBroker
from pirn.domains.data.identifier_validator import IdentifierValidator
from pirn.nodes.sub_tapestry import SubTapestry


class CDCDebezium(SubTapestry):
    """Apply Debezium change events from a broker topic to a target table."""

    def __init__(
        self,
        *,
        broker: MessageBroker,
        topic: str,
        target_pool: DatabaseConnectionPool,
        target_table: str,
        key_columns: Sequence[str],
        _config: KnotConfig,
        max_messages: int | None = None,
        **kwargs: Any,
    ) -> None:
        if not isinstance(broker, MessageBroker):
            raise TypeError(
                "CDCDebezium: broker must be a MessageBroker"
            )
        if not isinstance(target_pool, DatabaseConnectionPool):
            raise TypeError(
                "CDCDebezium: target_pool must be a DatabaseConnectionPool"
            )
        if not isinstance(topic, str) or not topic:
            raise ValueError("CDCDebezium: topic must be a non-empty string")
        IdentifierValidator.validate_column("target_table", target_table)
        key_tuple = tuple(key_columns)
        IdentifierValidator.validate_columns("key_columns", key_tuple)
        if max_messages is not None:
            if not isinstance(max_messages, int) or max_messages < 0:
                raise ValueError(
                    "CDCDebezium: max_messages must be None or a "
                    "non-negative integer"
                )
        self._broker = broker
        self._topic = topic
        self._target_pool = target_pool
        self._target_table = target_table
        self._key_columns = key_tuple
        self._max_messages = max_messages
        self._logger = logging.getLogger(self.__class__.__module__)
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> dict[str, Any]:
        """Consume Debezium change events from the broker topic and apply them to the target table.

        Returns:
            A dict with keys ``succeeded``, ``target_table``, ``applied``, and ``errors``
            summarising how many change events were applied.
        """
        applied = 0
        errors = 0
        consumed = 0
        async for record in await self._broker.consume(self._topic):
            envelope = self._decode_envelope(record)
            if envelope is None:
                errors += 1
            else:
                try:
                    await self._apply(envelope)
                    applied += 1
                except Exception:
                    self._logger.exception(
                        "cdc.debezium.apply_failed table=%s",
                        self._target_table,
                    )
                    errors += 1
            consumed += 1
            if (
                self._max_messages is not None
                and consumed >= self._max_messages
            ):
                break
        return {
            "succeeded": errors == 0,
            "target_table": self._target_table,
            "applied": applied,
            "errors": errors,
        }

    def _decode_envelope(self, record: Any) -> dict[str, Any] | None:
        value = getattr(record, "value", record)
        if isinstance(value, (bytes, bytearray)):
            try:
                value = value.decode("utf-8")
            except UnicodeDecodeError:
                self._logger.warning(
                    "cdc.debezium.decode_failed topic=%s reason=non_utf8",
                    self._topic,
                )
                return None
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                self._logger.warning(
                    "cdc.debezium.decode_failed topic=%s reason=invalid_json",
                    self._topic,
                )
                return None
        if not isinstance(value, dict):
            self._logger.warning(
                "cdc.debezium.decode_failed topic=%s reason=not_object",
                self._topic,
            )
            return None
        return value

    async def _apply(self, envelope: dict[str, Any]) -> None:
        op = envelope.get("op")
        before = envelope.get("before") or {}
        after = envelope.get("after") or {}
        if op in ("c", "r"):
            await self._apply_insert(after)
        elif op == "u":
            key_source = after if after else before
            await self._apply_update(after, key_source)
        elif op == "d":
            await self._apply_delete(before)
        else:
            raise ValueError(
                f"CDCDebezium: unsupported op {op!r} in envelope"
            )

    async def _apply_insert(self, after: dict[str, Any]) -> None:
        if not after:
            raise ValueError(
                "CDCDebezium: insert envelope missing 'after' payload"
            )
        for column in after:
            IdentifierValidator.validate_column("after column", column)
        columns = tuple(after.keys())
        placeholders = ", ".join(["?"] * len(columns))
        column_list = ", ".join(columns)
        query = (
            f"INSERT INTO {self._target_table} ({column_list}) "
            f"VALUES ({placeholders})"
        )
        await self._target_pool.execute(query, tuple(after[c] for c in columns))

    async def _apply_update(
        self,
        after: dict[str, Any],
        key_source: dict[str, Any],
    ) -> None:
        if not after:
            raise ValueError(
                "CDCDebezium: update envelope missing 'after' payload"
            )
        non_key_columns = tuple(c for c in after if c not in self._key_columns)
        if not non_key_columns:
            return  # nothing to update
        for column in non_key_columns:
            IdentifierValidator.validate_column("after column", column)
        set_clause = ", ".join(f"{c} = ?" for c in non_key_columns)
        where_clause = " AND ".join(f"{c} = ?" for c in self._key_columns)
        key_values = tuple(key_source.get(k) for k in self._key_columns)
        non_key_values = tuple(after[c] for c in non_key_columns)
        query = (
            f"UPDATE {self._target_table} SET {set_clause} "
            f"WHERE {where_clause}"
        )
        await self._target_pool.execute(query, non_key_values + key_values)

    async def _apply_delete(self, before: dict[str, Any]) -> None:
        if not before:
            raise ValueError(
                "CDCDebezium: delete envelope missing 'before' payload"
            )
        where_clause = " AND ".join(f"{c} = ?" for c in self._key_columns)
        key_values = tuple(before.get(k) for k in self._key_columns)
        query = f"DELETE FROM {self._target_table} WHERE {where_clause}"
        await self._target_pool.execute(query, key_values)
