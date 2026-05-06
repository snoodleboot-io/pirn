"""Unit tests for :class:`ParsedTraceHeader`."""

from __future__ import annotations

import unittest

from pirn.domains.oilgas.types.parsed_trace_header import ParsedTraceHeader


class TestConstruction(unittest.TestCase):
    def test_default_values(self) -> None:
        header = ParsedTraceHeader()
        assert header.inline == 0
        assert header.xline == 0
        assert header.cdp_x == 0.0
        assert header.cdp_y == 0.0
        assert header.source_x == 0.0
        assert header.source_y == 0.0
        assert header.receiver_x == 0.0
        assert header.receiver_y == 0.0

    def test_full_values(self) -> None:
        header = ParsedTraceHeader(
            inline=5,
            xline=7,
            cdp_x=100.0,
            cdp_y=200.0,
            source_x=10.0,
            source_y=20.0,
            receiver_x=30.0,
            receiver_y=40.0,
        )
        assert header.inline == 5
        assert header.xline == 7
        assert header.cdp_x == 100.0
        assert header.receiver_y == 40.0


class TestAuditDict(unittest.TestCase):
    def test_audit_dict_keys(self) -> None:
        header = ParsedTraceHeader(inline=1, xline=2)
        d = header._pirn_audit_dict()
        assert d["inline"] == 1
        assert d["xline"] == 2
        assert d["cdp_x"] == 0.0
        assert "receiver_x" in d
        assert "receiver_y" in d


class TestFrozen(unittest.TestCase):
    def test_frozen_disallows_mutation(self) -> None:
        header = ParsedTraceHeader(inline=1)
        try:
            header.inline = 9  # type: ignore[misc]
        except Exception:
            return
        raise AssertionError("ParsedTraceHeader must be frozen")
