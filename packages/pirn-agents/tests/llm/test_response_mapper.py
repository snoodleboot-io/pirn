"""Unit tests for :class:`pirn_agents.llm.response_mapper.ResponseMapper`.

Exercises the extracted response-mapping collaborator in isolation: folding
extracted primitives into an :class:`AgentResponse` (tool-call decoding via the
codec, cost estimation via optional pricing) and rendering a response back into
a plain mapping.
"""

from __future__ import annotations

import unittest
from typing import Any

from pirn_agents.llm.model_pricing import ModelPricing
from pirn_agents.llm.provider_adapter import ProviderAdapter
from pirn_agents.llm.response_mapper import ResponseMapper
from pirn_agents.tools.tool_call_codec import ToolCallCodec
from pirn_agents.types.agent_response import AgentResponse
from pirn_agents.types.tool_call import ToolCall


class _StubToolAdapter(ProviderAdapter):
    """Trivial adapter: the provider message is already a list of call dicts."""

    def tool_to_native(self, neutral_tool: dict[str, Any]) -> dict[str, Any]:
        return dict(neutral_tool)

    def extract_tool_calls(self, provider_msg: Any) -> list[dict[str, Any]]:
        return list(provider_msg)

    def result_to_native(self, result_payload: dict[str, Any]) -> Any:
        return dict(result_payload)


def _mapper(pricing: ModelPricing | None = None) -> ResponseMapper:
    return ResponseMapper(codec=ToolCallCodec(_StubToolAdapter()), pricing=pricing)


class TestToAgentResponse(unittest.TestCase):
    def test_maps_primitives_and_decodes_tool_calls(self) -> None:
        # Arrange
        mapper = _mapper()
        tool_message = [{"id": "c1", "name": "search", "arguments": {"q": "cats"}}]

        # Act
        response = mapper.to_agent_response(
            content="hello",
            tool_message=tool_message,
            finish_reason="tool_use",
            usage={"input_tokens": 10, "output_tokens": 4},
        )

        # Assert
        assert response.content == "hello"
        assert response.finish_reason == "tool_use"
        assert response.usage == {"input_tokens": 10, "output_tokens": 4}
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0].tool_name == "search"
        assert response.tool_calls[0].arguments == {"q": "cats"}
        assert response.cost is None

    def test_cost_estimated_when_pricing_configured(self) -> None:
        # Arrange
        mapper = _mapper(ModelPricing(input_per_million=1000.0, output_per_million=2000.0))

        # Act
        response = mapper.to_agent_response(
            content="",
            tool_message=[],
            finish_reason="stop",
            usage={"input_tokens": 10, "output_tokens": 4},
        )

        # Assert: (10 * 1000 + 4 * 2000) / 1e6 = 0.018
        assert response.cost == 0.018


class TestEstimateCostAndMapping(unittest.TestCase):
    def test_estimate_cost_is_none_without_pricing(self) -> None:
        # Arrange / Act / Assert
        assert _mapper().estimate_cost({"input_tokens": 5}) is None

    def test_estimate_cost_uses_pricing(self) -> None:
        # Arrange
        mapper = _mapper(ModelPricing(input_per_million=1_000_000.0, output_per_million=0.0))

        # Act / Assert
        assert mapper.estimate_cost({"input_tokens": 2, "output_tokens": 9}) == 2.0

    def test_to_mapping_renders_flat_dict(self) -> None:
        # Arrange
        response = AgentResponse(
            content="hi",
            tool_calls=(ToolCall(tool_name="t", arguments={"a": 1}, call_id="c1"),),
            finish_reason="stop",
            usage={"input_tokens": 1},
            cost=0.5,
        )

        # Act
        mapping = ResponseMapper.to_mapping(response)

        # Assert
        assert mapping == {
            "content": "hi",
            "tool_calls": [{"a": 1}],
            "finish_reason": "stop",
            "usage": {"input_tokens": 1},
            "cost": 0.5,
        }


if __name__ == "__main__":
    unittest.main()
