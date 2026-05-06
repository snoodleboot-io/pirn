"""Unit tests for :class:`_AnalysisStep`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.specialized_agents._analysis_step import (
    _AnalysisStep,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import StubLLMProvider


class TestAnalysisStepProcess(unittest.IsolatedAsyncioTestCase):
    async def test_combines_sql_result_and_analysis(self) -> None:
        llm = StubLLMProvider(["Revenue grew 10%."])
        sql_response = AgentResponse(
            content="SQL:\nSELECT SUM(revenue)\n\nRows (1):\n(100000,)",
            finish_reason="stop",
        )
        with Tapestry() as t:
            _AnalysisStep(
                question="What is total revenue?",
                sql_response=sql_response,
                llm=llm,
                _config=KnotConfig(id="as"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["as"]
        assert isinstance(out, AgentResponse)
        assert "Analysis:" in out.content
        assert "Revenue grew 10%." in out.content

    async def test_rejects_non_agent_response(self) -> None:
        llm = StubLLMProvider(["x"])
        with Tapestry():
            k = _AnalysisStep.__new__(_AnalysisStep)
            object.__setattr__(k, "_config", KnotConfig(id="as"))
        with self.assertRaises((TypeError, ValueError)):
            await k.process(
                question="q",
                sql_response="not-a-response",  # type: ignore[arg-type]
                llm=llm,
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_process_rejects_non_agent_response(self) -> None:
        llm = StubLLMProvider(["x"])
        with Tapestry():
            k = _AnalysisStep.__new__(_AnalysisStep)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises(TypeError):
            await k.process(
                question="q",
                sql_response="not-an-agent-response",  # type: ignore[arg-type]
                llm=llm,
            )
