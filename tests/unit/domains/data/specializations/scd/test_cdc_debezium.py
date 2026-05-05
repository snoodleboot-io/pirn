"""Tests for :class:`CDCDebezium`."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.connectors.message_broker import MessageBroker
from pirn.domains.data.specializations.scd.cdc_debezium import CDCDebezium


def _make_broker() -> MagicMock:
    return MagicMock(spec=MessageBroker)


def _make_pool() -> MagicMock:
    return MagicMock(spec=DatabaseConnectionPool)


class TestCDCDebeziumConstruction(unittest.TestCase):
    def test_valid_construction(self) -> None:
        cdc = CDCDebezium(
            broker=_make_broker(),
            topic="orders.cdc",
            target_pool=_make_pool(),
            target_table="orders",
            key_columns=["id"],
            _config=KnotConfig(id="cdc"),
        )
        self.assertIsInstance(cdc, CDCDebezium)

    def test_rejects_non_broker(self) -> None:
        with self.assertRaises(TypeError):
            CDCDebezium(
                broker="not-broker",  # type: ignore[arg-type]
                topic="orders.cdc",
                target_pool=_make_pool(),
                target_table="orders",
                key_columns=["id"],
                _config=KnotConfig(id="cdc"),
            )

    def test_rejects_non_pool_target(self) -> None:
        with self.assertRaises(TypeError):
            CDCDebezium(
                broker=_make_broker(),
                topic="orders.cdc",
                target_pool="not-pool",  # type: ignore[arg-type]
                target_table="orders",
                key_columns=["id"],
                _config=KnotConfig(id="cdc"),
            )

    def test_rejects_empty_topic(self) -> None:
        with self.assertRaises(ValueError):
            CDCDebezium(
                broker=_make_broker(),
                topic="",
                target_pool=_make_pool(),
                target_table="orders",
                key_columns=["id"],
                _config=KnotConfig(id="cdc"),
            )

    def test_rejects_negative_max_messages(self) -> None:
        with self.assertRaises(ValueError):
            CDCDebezium(
                broker=_make_broker(),
                topic="orders.cdc",
                target_pool=_make_pool(),
                target_table="orders",
                key_columns=["id"],
                max_messages=-1,
                _config=KnotConfig(id="cdc"),
            )

    def test_accepts_zero_max_messages(self) -> None:
        cdc = CDCDebezium(
            broker=_make_broker(),
            topic="orders.cdc",
            target_pool=_make_pool(),
            target_table="orders",
            key_columns=["id"],
            max_messages=0,
            _config=KnotConfig(id="cdc"),
        )
        self.assertIsInstance(cdc, CDCDebezium)


class TestCDCDebeziumDecodeEnvelope(unittest.TestCase):
    def _make_cdc(self) -> CDCDebezium:
        return CDCDebezium(
            broker=_make_broker(),
            topic="orders.cdc",
            target_pool=_make_pool(),
            target_table="orders",
            key_columns=["id"],
            _config=KnotConfig(id="cdc"),
        )

    def test_decodes_dict_envelope(self) -> None:
        cdc = self._make_cdc()
        env = {"op": "c", "after": {"id": 1}}
        result = cdc._decode_envelope(env)
        self.assertEqual(result, env)

    def test_decodes_json_bytes(self) -> None:
        import json
        cdc = self._make_cdc()
        env = {"op": "u", "after": {"id": 2}, "before": {"id": 2}}
        record = MagicMock()
        record.value = json.dumps(env).encode()
        result = cdc._decode_envelope(record)
        self.assertEqual(result["op"], "u")

    def test_returns_none_for_invalid_json(self) -> None:
        cdc = self._make_cdc()
        record = MagicMock()
        record.value = b"not-json"
        result = cdc._decode_envelope(record)
        self.assertIsNone(result)

    def test_returns_none_for_non_object(self) -> None:
        cdc = self._make_cdc()
        record = MagicMock()
        record.value = b"[1, 2, 3]"
        result = cdc._decode_envelope(record)
        self.assertIsNone(result)
