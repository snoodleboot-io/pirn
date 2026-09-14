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
        assert response.data == "hi"
        assert response.metadata.tool_calls == ()
        assert response.metadata.finish_reason == "stop"
        assert dict(response.metadata.usage) == {}

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
        assert response.metadata.tool_calls == (call,)
        assert response.metadata.finish_reason == "tool_use"
        assert response.metadata.usage["input_tokens"] == 10
        assert response.metadata.cost == 0.02
        assert response.metadata.model == "claude-sonnet-5"
        assert response.metadata.provider == "anthropic"

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
        assert response.metadata is response.metadata
        assert response.data == "hi"
        assert response.data == response.data

    def test_derive_inherits_frame_and_overrides(self) -> None:
        call = ToolCall(tool_name="t", arguments={}, call_id="c1")
        original = AgentResponse(
            content="a", tool_calls=(call,), finish_reason="tool_use", model="m1"
        )
        derived = original.derive("b", tool_calls=())
        assert derived.data == "b"
        assert derived.metadata.tool_calls == ()
        assert derived.metadata.finish_reason == "tool_use"
        assert derived.metadata.model == "m1"


class TestNoFieldNameAliases(unittest.TestCase):
    def test_fields_are_read_through_payload_access_only(self) -> None:
        # Arrange: the constructor's field names, plus the old ``frame`` alias of ``metadata``.
        names = (
            "frame",
            "content",
            "tool_calls",
            "finish_reason",
            "usage",
            "cost",
            "model",
            "provider",
        )

        # Act.
        aliases = [name for name in names if hasattr(AgentResponse, name)]

        # Assert: PIR-872 deleted every alias; read ``.data`` / ``.metadata.<field>``.
        self.assertEqual(aliases, [])
