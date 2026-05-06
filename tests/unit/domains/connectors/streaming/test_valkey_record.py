"""Tests for :class:`ValkeyRecord`."""

from __future__ import annotations

import unittest

from pirn.domains.connectors.streaming.valkey_record import ValkeyRecord


def _make_record(**fields: bytes) -> ValkeyRecord:
    return ValkeyRecord(
        entry_id=b"1234-0",
        stream="events",
        fields={k.encode(): v for k, v in fields.items()},
    )


class TestValkeyRecord(unittest.TestCase):
    def test_id_property(self) -> None:
        rec = ValkeyRecord(entry_id=b"abc", stream="s", fields={})
        self.assertEqual(rec.id, b"abc")

    def test_stream_property(self) -> None:
        rec = ValkeyRecord(entry_id=b"abc", stream="my-stream", fields={})
        self.assertEqual(rec.stream, "my-stream")

    def test_value_from_v_field(self) -> None:
        rec = ValkeyRecord(entry_id=b"1", stream="s", fields={b"v": b"hello"})
        self.assertEqual(rec.value, b"hello")

    def test_value_default_empty(self) -> None:
        rec = ValkeyRecord(entry_id=b"1", stream="s", fields={})
        self.assertEqual(rec.value, b"")

    def test_key_from_k_field(self) -> None:
        rec = ValkeyRecord(entry_id=b"1", stream="s", fields={b"k": b"mykey"})
        self.assertEqual(rec.key, b"mykey")

    def test_key_none_when_absent(self) -> None:
        rec = ValkeyRecord(entry_id=b"1", stream="s", fields={b"v": b"x"})
        self.assertIsNone(rec.key)

    def test_headers_decoded_from_h_prefix(self) -> None:
        rec = ValkeyRecord(
            entry_id=b"1",
            stream="s",
            fields={b"v": b"x", b"h:trace-id": b"abc123"},
        )
        self.assertEqual(rec.headers, {"trace-id": b"abc123"})

    def test_headers_empty_when_none_set(self) -> None:
        rec = ValkeyRecord(entry_id=b"1", stream="s", fields={b"v": b"x"})
        self.assertEqual(rec.headers, {})

    def test_fields_property(self) -> None:
        fields = {b"v": b"x"}
        rec = ValkeyRecord(entry_id=b"1", stream="s", fields=fields)
        self.assertIs(rec.fields, fields)
