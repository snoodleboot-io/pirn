"""Unit tests for :class:`AgentResponse`."""

from __future__ import annotations

import unittest

from pirn.core.payload import Payload

from pirn_agents.tools.tool_call import ToolCall
from pirn_agents.types.messaging.agent_response import AgentResponse
from pirn_agents.types.messaging.generation_frame import GenerationFrame


class TestRoundtrip(unittest.TestCase):
    def test_construct_defaults(self) -> None:
        response = AgentResponse(content="hi")
        assert response.content == "hi"
        assert response.tool_calls == ()
        assert response.finish_reason == "stop"
        assert dict(response.usage) == {}

    def test_construct_full_fields(self) -> None:
        call = ToolCall(tool_name="t", arguments={}, call_id="c1")
        response = AgentResponse(
            content="ok",
            tool_calls=(call,),
            finish_reason="tool_use",
            usage={"input_tokens": 10, "output_tokens": 5},
            cost=0.02,
            model="claude-sonnet-5",
            provider="anthropic",
        )
        assert response.tool_calls == (call,)
        assert response.finish_reason == "tool_use"
        assert response.usage["input_tokens"] == 10
        assert response.cost == 0.02
        assert response.model == "claude-sonnet-5"
        assert response.provider == "anthropic"

    def test_audit_dict_includes_tool_calls(self) -> None:
        call = ToolCall(tool_name="t", arguments={}, call_id="c1")
        response = AgentResponse(content="hi", tool_calls=(call,))
        d = response._pirn_audit_dict()
        assert d["tool_calls"][0]["tool_name"] == "t"
        assert d["finish_reason"] == "stop"
        assert d["content"] == "hi"


class TestPayloadShape(unittest.TestCase):
    def test_is_a_payload_of_generation_frame_and_str(self) -> None:
        response = AgentResponse(content="hi")
        assert isinstance(response, Payload)
        assert isinstance(response.metadata, GenerationFrame)
        assert response.metadata is response.frame
        assert response.data == "hi"
        assert response.data == response.content

    def test_derive_inherits_frame_and_overrides(self) -> None:
        call = ToolCall(tool_name="t", arguments={}, call_id="c1")
        original = AgentResponse(
            content="a", tool_calls=(call,), finish_reason="tool_use", model="m1"
        )
        derived = original.derive("b", tool_calls=())
        assert derived.content == "b"
        assert derived.tool_calls == ()
        assert derived.finish_reason == "tool_use"
        assert derived.model == "m1"
