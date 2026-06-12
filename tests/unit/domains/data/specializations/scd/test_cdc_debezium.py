"""Tests for :class:`CDCDebezium`."""

from __future__ import annotations

import json
import unittest
from typing import Any
from unittest.mock import MagicMock

from pirn.core.knot_config import KnotConfig
from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.connectors.message_broker import MessageBroker
from pirn.domains.data.specializations.scd.cdc_debezium import CDCDebezium
from pirn.tapestry import Tapestry


def _make_broker() -> MagicMock:
    return MagicMock(spec=MessageBroker)


def _make_pool() -> MagicMock:
    return MagicMock(spec=DatabaseConnectionPool)


def _make_knot(**kwargs: Any) -> CDCDebezium:
    defaults: dict[str, Any] = {
        "broker": _make_broker(),
        "topic": "orders.cdc",
        "target_pool": _make_pool(),
        "target_table": "orders",
        "key_columns": ("id",),
    }
    defaults.update(kwargs)
    with Tapestry():
        return CDCDebezium(**defaults, _config=KnotConfig(id="cdc"))


class TestCDCDebeziumConstruction(unittest.TestCase):
    def test_valid_construction(self) -> None:
        cdc = _make_knot()
        self.assertIsInstance(cdc, CDCDebezium)

    def test_accepts_zero_max_messages(self) -> None:
        cdc = _make_knot(max_messages=0)
        self.assertIsInstance(cdc, CDCDebezium)


class TestCDCDebeziumDecodeEnvelope(unittest.TestCase):
    def test_decodes_dict_envelope(self) -> None:
        env = {"op": "c", "after": {"id": 1}}
        result = CDCDebezium._decode_envelope(env, "orders.cdc")
        self.assertEqual(result, env)

    def test_decodes_json_bytes(self) -> None:
        env = {"op": "u", "after": {"id": 2}, "before": {"id": 2}}
        record = MagicMock()
        record.value = json.dumps(env).encode()
        result = CDCDebezium._decode_envelope(record, "orders.cdc")
        assert result is not None
        self.assertEqual(result["op"], "u")

    def test_returns_none_for_invalid_json(self) -> None:
        record = MagicMock()
        record.value = b"not-json"
        result = CDCDebezium._decode_envelope(record, "orders.cdc")
        self.assertIsNone(result)

    def test_returns_none_for_non_object(self) -> None:
        record = MagicMock()
        record.value = b"[1, 2, 3]"
        result = CDCDebezium._decode_envelope(record, "orders.cdc")
        self.assertIsNone(result)


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, **kwargs: Any) -> CDCDebezium:
        return _make_knot(**kwargs)

    async def _call(self, k: CDCDebezium, **overrides: Any) -> None:
        args: dict[str, Any] = {
            "broker": _make_broker(),
            "topic": "orders.cdc",
            "target_pool": _make_pool(),
            "target_table": "orders",
            "key_columns": ("id",),
        }
        args.update(overrides)
        await k.process(**args)

    async def test_rejects_non_broker(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(TypeError, "MessageBroker"):
            await self._call(k, broker="not-broker")

    async def test_rejects_non_pool_target(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(TypeError, "DatabaseConnectionPool"):
            await self._call(k, target_pool="not-pool")

    async def test_rejects_empty_topic(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "topic"):
            await self._call(k, topic="")

    async def test_rejects_negative_max_messages(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "max_messages"):
            await self._call(k, max_messages=-1)
