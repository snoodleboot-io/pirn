"""Unit tests for :class:`RAGResponseBuilder`."""

from __future__ import annotations

from typing import Any
import unittest

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.rag.rag_response_builder import (
    RAGResponseBuilder,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry


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
