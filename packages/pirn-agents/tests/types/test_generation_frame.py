"""Unit tests for :class:`GenerationFrame`."""

from __future__ import annotations

import unittest

from pirn_agents.tools.tool_call import ToolCall
from pirn_agents.types.messaging.generation_frame import GenerationFrame


class TestRoundtrip(unittest.TestCase):
    def test_defaults(self) -> None:
        frame = GenerationFrame()
        assert frame.finish_reason == "stop"
        assert dict(frame.usage) == {}
        assert frame.cost is None
        assert frame.tool_calls == ()
        assert frame.model is None
        assert frame.provider is None

    def test_audit_dict(self) -> None:
        call = ToolCall(tool_name="t", arguments={}, call_id="c1")
        frame = GenerationFrame(
            finish_reason="tool_use",
            usage={"input_tokens": 1},
            cost=0.5,
            tool_calls=(call,),
            model="m1",
            provider="p1",
        )
        d = frame._pirn_audit_dict()
        assert d == {
            "finish_reason": "tool_use",
            "usage": {"input_tokens": 1},
            "cost": 0.5,
            "tool_calls": [call._pirn_audit_dict()],
            "model": "m1",
            "provider": "p1",
        }
