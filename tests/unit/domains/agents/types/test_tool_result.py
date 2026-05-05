"""Unit tests for :class:`ToolResult`."""

from __future__ import annotations
import unittest

from pirn.domains.agents.types.tool_result import ToolResult


class TestRoundtrip(unittest.TestCase):
    def test_construct_success(self) -> None:
        result = ToolResult(call_id="c1", result={"answer": 42}, error=None)
        assert result.call_id == "c1"
        assert result.result == {"answer": 42}
        assert result.error is None

    def test_construct_failure(self) -> None:
        result = ToolResult(call_id="c1", result=None, error="boom")
        assert result.error == "boom"
        assert result.result is None

    def test_audit_dict_includes_repr_of_result(self) -> None:
        result = ToolResult(call_id="c1", result={"x": 1}, error=None)
        d = result._pirn_audit_dict()
        assert d["call_id"] == "c1"
        assert d["error"] is None
