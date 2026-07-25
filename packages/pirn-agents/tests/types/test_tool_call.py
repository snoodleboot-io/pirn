"""Unit tests for :class:`ToolCall`."""

from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError

from pirn_agents.types.tool_call import ToolCall


class TestRoundtrip(unittest.TestCase):
    def test_construct_minimum_fields(self) -> None:
        call = ToolCall(tool_name="search", arguments={"q": "x"}, call_id="call-1")
        assert call.tool_name == "search"
        assert call.arguments == {"q": "x"}
        assert call.call_id == "call-1"
        assert call.raw is None

    def test_audit_dict_round_trip(self) -> None:
        call = ToolCall(tool_name="t", arguments={"a": 1}, call_id="id")
        d = call._pirn_audit_dict()
        assert d == {
            "tool_name": "t",
            "arguments": {"a": 1},
            "call_id": "id",
            "raw": None,
        }


class TestRawField(unittest.TestCase):
    def test_construct_with_raw(self) -> None:
        raw = {"type": "tool_use", "id": "abc"}
        call = ToolCall(tool_name="t", arguments={}, call_id="c1", raw=raw)
        assert call.raw == raw

    def test_audit_dict_reprs_raw(self) -> None:
        raw = {"k": "v"}
        call = ToolCall(tool_name="t", arguments={}, call_id="c1", raw=raw)
        d = call._pirn_audit_dict()
        assert d["raw"] == repr(raw)

    def test_frozen(self) -> None:
        call = ToolCall(tool_name="t", arguments={}, call_id="c1")
        with self.assertRaises(FrozenInstanceError):
            call.tool_name = "other"  # type: ignore[misc]
