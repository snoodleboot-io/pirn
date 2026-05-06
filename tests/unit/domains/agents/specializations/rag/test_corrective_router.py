"""Unit tests for :class:`CorrectiveRouter`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.rag.corrective_router import (
    CorrectiveRouter,
)
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import StubTool


class TestCorrectiveRouterConstruction(unittest.TestCase):
    def test_rejects_non_tool_fallback(self) -> None:
        with self.assertRaisesRegex(TypeError, "Tool"):
            with Tapestry():
                CorrectiveRouter(
                    query="q",
                    relevant_docs=[],
                    fallback_tool="not-a-tool",  # type: ignore[arg-type]
                    _config=KnotConfig(id="cr"),
                )


class TestCorrectiveRouterProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_relevant_docs_when_non_empty(self) -> None:
        tool = StubTool(name="web_search")
        docs = [{"text": "relevant"}]
        with Tapestry() as t:
            CorrectiveRouter(
                query="question",
                relevant_docs=docs,
                fallback_tool=tool,
                _config=KnotConfig(id="cr"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["cr"] == docs
        assert len(tool.invocations) == 0

    async def test_invokes_fallback_when_no_docs(self) -> None:
        tool = StubTool(name="web_search", handler="fallback result")
        with Tapestry() as t:
            CorrectiveRouter(
                query="question",
                relevant_docs=[],
                fallback_tool=tool,
                _config=KnotConfig(id="cr"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["cr"]
        assert len(out) == 1
        assert out[0]["source"] == "fallback"
        assert "fallback result" in out[0]["content"]
        assert len(tool.invocations) == 1

    async def test_rejects_non_string_query(self) -> None:
        tool = StubTool(name="web_search")
        with Tapestry():
            with self.assertRaises(TypeError):
                CorrectiveRouter(
                    query=42,  # type: ignore[arg-type]
                    relevant_docs=[],
                    fallback_tool=tool,
                    _config=KnotConfig(id="cr"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_process_rejects_non_tool_fallback(self) -> None:
        with Tapestry():
            k = CorrectiveRouter.__new__(CorrectiveRouter)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises(TypeError):
            await k.process(query="q", relevant_docs=[], fallback_tool="not-a-tool")  # type: ignore[arg-type]

    async def test_process_rejects_non_string_query(self) -> None:
        tool = StubTool(name="web_search")
        with Tapestry():
            k = CorrectiveRouter.__new__(CorrectiveRouter)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises(TypeError):
            await k.process(query=99, relevant_docs=[], fallback_tool=tool)  # type: ignore[arg-type]
