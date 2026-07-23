"""Unit tests for :class:`ToolResult`."""

from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError

from pirn_agents.types.tool_result import ToolResult
from pirn_agents.types.tool_status import ToolStatus


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


class TestStatusFields(unittest.TestCase):
    def test_default_status_ok(self) -> None:
        result = ToolResult(call_id="c1", result=42)
        assert result.status is ToolStatus.OK
        assert result.latency is None
        assert result.tokens is None

    def test_error_promotes_status_to_error(self) -> None:
        result = ToolResult(call_id="c1", result=None, error="boom")
        assert result.status is ToolStatus.ERROR

    def test_explicit_status_preserved_over_error(self) -> None:
        result = ToolResult(
            call_id="c1",
            result=None,
            error="timed out",
            status=ToolStatus.TIMEOUT,
        )
        assert result.status is ToolStatus.TIMEOUT

    def test_explicit_nonok_status_without_error_is_untouched(self) -> None:
        result = ToolResult(call_id="c1", result=None, status=ToolStatus.TIMEOUT)
        assert result.status is ToolStatus.TIMEOUT

    def test_latency_and_tokens_round_trip(self) -> None:
        result = ToolResult(call_id="c1", result=1, latency=0.25, tokens=17)
        assert result.latency == 0.25
        assert result.tokens == 17

    def test_audit_dict_includes_new_fields(self) -> None:
        result = ToolResult(call_id="c1", result="x", error="e", latency=1.5, tokens=3)
        d = result._pirn_audit_dict()
        assert d == {
            "call_id": "c1",
            "result": repr("x"),
            "error": "e",
            "status": "error",
            "latency": 1.5,
            "tokens": 3,
        }

    def test_frozen(self) -> None:
        result = ToolResult(call_id="c1", result=1)
        with self.assertRaises(FrozenInstanceError):
            result.result = 2  # type: ignore[misc]

    def test_cache_stability_identical_fields_equal_audit(self) -> None:
        a = ToolResult(call_id="c1", result=1, latency=0.1, tokens=5)
        b = ToolResult(call_id="c1", result=1, latency=0.1, tokens=5)
        assert a._pirn_audit_dict() == b._pirn_audit_dict()
        assert a == b
