"""Unit tests for :class:`AnalysisStep`."""

from __future__ import annotations

import unittest

from pirn.core.err import Err
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.specializations.specialized_agents.analysis_step import (
    AnalysisStep,
)
from pirn_agents.types.messaging.agent_response import AgentResponse
from tests.specializations.conftest import StubLLMProvider


class TestAnalysisStepProcess(unittest.IsolatedAsyncioTestCase):
    async def test_combines_sql_result_and_analysis(self) -> None:
        llm = StubLLMProvider(["Revenue grew 10%."])
        sql_response = AgentResponse(
            content="SQL:\nSELECT SUM(revenue)\n\nRows (1):\n(100000,)",
            finish_reason="stop",
        )
        with Tapestry() as t:
            AnalysisStep(
                question="What is total revenue?",
                sql_response=sql_response,
                llm=llm,
                _config=KnotConfig(id="as"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["as"]
        assert isinstance(out, AgentResponse)
        assert "Analysis:" in out.data
        assert "Revenue grew 10%." in out.data

    async def test_rejects_non_agent_response(self) -> None:
        llm = StubLLMProvider(["x"])
        valid_response = AgentResponse(content="ok", finish_reason="stop")
        with Tapestry():
            k = AnalysisStep(
                question="q",
                sql_response=valid_response,
                llm=llm,
                _config=KnotConfig(id="as"),
            )
        result = await k(
            {
                "question": "q",
                "sql_response": "not-a-response",
                "llm": llm,
            }
        )
        assert isinstance(result, Err)
        assert result.record.exc_type == "ValidationError"


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_process_rejects_non_agent_response(self) -> None:
        llm = StubLLMProvider(["x"])
        valid_response = AgentResponse(content="ok", finish_reason="stop")
        with Tapestry():
            k = AnalysisStep(
                question="q", sql_response=valid_response, llm=llm, _config=KnotConfig(id="x")
            )
        result = await k({"question": "q", "sql_response": "not-an-agent-response", "llm": llm})
        assert isinstance(result, Err)
        assert result.record.exc_type == "ValidationError"
