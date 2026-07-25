"""Tests for :mod:`pirn_agents.agent_response_mapper`."""

from __future__ import annotations

import unittest

from pirn_agents.agent_response_mapper import AgentResponseMapper
from pirn_agents.types.agent_response import AgentResponse
from pirn_agents.types.tool_status import ToolStatus


class TestSummariseTokens(unittest.TestCase):
    def test_prefers_total_tokens(self) -> None:
        self.assertEqual(
            AgentResponseMapper().summarise_tokens({"total_tokens": 11, "input_tokens": 4}), 11
        )

    def test_sums_input_and_output_when_no_total(self) -> None:
        self.assertEqual(
            AgentResponseMapper().summarise_tokens({"input_tokens": 4, "output_tokens": 7}), 11
        )

    def test_returns_none_for_empty_usage(self) -> None:
        self.assertIsNone(AgentResponseMapper().summarise_tokens({}))

    def test_returns_none_for_unrecognised_fields(self) -> None:
        self.assertIsNone(AgentResponseMapper().summarise_tokens({"cache_reads": 3}))


class TestAgentResponseToToolResult(unittest.TestCase):
    def test_passes_full_response_through_as_result(self) -> None:
        response = AgentResponse(content="hi", usage={"input_tokens": 1, "output_tokens": 2})

        result = AgentResponseMapper().to_tool_result(response, call_id="c1", latency=0.5)

        self.assertIs(result.result, response)
        self.assertEqual(result.call_id, "c1")
        self.assertEqual(result.status, ToolStatus.OK)
        self.assertEqual(result.latency, 0.5)
        self.assertEqual(result.tokens, 3)

    def test_tokens_none_when_no_usage(self) -> None:
        result = AgentResponseMapper().to_tool_result(AgentResponse(content="hi"), call_id="c1")

        self.assertIsNone(result.tokens)
        self.assertIsNone(result.error)
