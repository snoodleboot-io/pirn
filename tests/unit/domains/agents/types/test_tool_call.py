"""Unit tests for :class:`ToolCall`."""

from __future__ import annotations
import unittest

from pirn.domains.agents.types.tool_call import ToolCall


class TestRoundtrip(unittest.TestCase):
    def test_construct_minimum_fields(self) -> None:
        call = ToolCall(tool_name="search", arguments={"q": "x"}, call_id="call-1")
        assert call.tool_name == "search"
        assert call.arguments == {"q": "x"}
        assert call.call_id == "call-1"

    def test_audit_dict_round_trip(self) -> None:
        call = ToolCall(tool_name="t", arguments={"a": 1}, call_id="id")
        d = call._pirn_audit_dict()
        assert d == {"tool_name": "t", "arguments": {"a": 1}, "call_id": "id"}
