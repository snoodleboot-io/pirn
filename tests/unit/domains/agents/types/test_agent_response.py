"""Unit tests for :class:`AgentResponse`."""

from __future__ import annotations

from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.domains.agents.types.tool_call import ToolCall


class TestRoundtrip:
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
        )
        assert response.tool_calls == (call,)
        assert response.finish_reason == "tool_use"
        assert response.usage["input_tokens"] == 10

    def test_audit_dict_includes_tool_calls(self) -> None:
        call = ToolCall(tool_name="t", arguments={}, call_id="c1")
        response = AgentResponse(content="hi", tool_calls=(call,))
        d = response._pirn_audit_dict()
        assert d["tool_calls"][0]["tool_name"] == "t"
        assert d["finish_reason"] == "stop"
