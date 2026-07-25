"""Unit tests for :class:`RAGResponseBuilder`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.specializations.rag.rag_response_builder import (
    RAGResponseBuilder,
)
from pirn_agents.types.agent_response import AgentResponse


class _AnswerSource(Knot):
    def __init__(self, answer, *, _config, **kwargs):
        self._answer = answer
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any):
        return self._answer


class TestRAGResponseBuilderProcess(unittest.IsolatedAsyncioTestCase):
    async def test_wraps_answer_in_agent_response(self) -> None:
        with Tapestry() as t:
            src = _AnswerSource("The answer is 42.", _config=KnotConfig(id="src"))
            RAGResponseBuilder(
                answer=src,
                _config=KnotConfig(id="rrb"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["rrb"]
        assert isinstance(out, AgentResponse)
        assert out.content == "The answer is 42."
        assert out.finish_reason == "stop"

    async def test_rejects_non_string_answer(self) -> None:
        with Tapestry() as t:
            src = _AnswerSource(42, _config=KnotConfig(id="src"))
            RAGResponseBuilder(
                answer=src,
                _config=KnotConfig(id="rrb"),
            )
        result = await t.run(RunRequest())
        assert not result.succeeded


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_process_rejects_non_string_answer(self) -> None:
        with Tapestry():
            k = RAGResponseBuilder.__new__(RAGResponseBuilder)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises(TypeError):
            await k.process(answer=42)  # type: ignore[arg-type]

    async def test_process_returns_agent_response(self) -> None:
        with Tapestry():
            k = RAGResponseBuilder.__new__(RAGResponseBuilder)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        result = await k.process(answer="hello world")
        assert isinstance(result, AgentResponse)
        assert result.content == "hello world"
        assert result.finish_reason == "stop"
