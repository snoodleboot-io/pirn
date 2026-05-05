"""Unit tests for :class:`AgentMessage`."""

from __future__ import annotations

from datetime import datetime, timezone
import unittest

from pirn.domains.agents.types.agent_message import AgentMessage


class TestRoundtrip(unittest.TestCase):
    def test_construct_minimum_fields(self) -> None:
        msg = AgentMessage(role="user", content="hello")
        assert msg.role == "user"
        assert msg.content == "hello"
        assert msg.tool_call_id is None
        assert msg.name is None

    def test_construct_full_fields(self) -> None:
        when = datetime(2026, 1, 1, tzinfo=timezone.utc)
        msg = AgentMessage(
            role="tool",
            content="42",
            name="calculator",
            tool_call_id="call-1",
            created_at=when,
        )
        assert msg.role == "tool"
        assert msg.tool_call_id == "call-1"
        assert msg.name == "calculator"
        assert msg.created_at == when

    def test_audit_dict_round_trip(self) -> None:
        msg = AgentMessage(role="user", content="hi")
        d = msg._pirn_audit_dict()
        assert d["role"] == "user"
        assert d["content"] == "hi"
        assert "created_at" in d

    def test_frozen_disallows_mutation(self) -> None:
        msg = AgentMessage(role="user", content="hi")
        try:
            msg.content = "bye"  # type: ignore[misc]
        except Exception:
            return
        raise AssertionError("AgentMessage should be frozen")
