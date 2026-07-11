"""Tests for :class:`ToolSelector`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.specializations.tool_use.tool_selector import ToolSelector
from tests.specializations.conftest import (
    StubLLMProvider,
    StubTool,
)


def _make_selector(
    message: str,
    tools: list,
    llm: StubLLMProvider,
) -> ToolSelector:
    with Tapestry():
        return ToolSelector(
            message=message,
            tools=tools,
            llm=llm,
            _config=KnotConfig(id="sel"),
        )


class TestToolSelectorValidation(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_llm_provider(self) -> None:
        tools = [StubTool(name="search")]
        llm = StubLLMProvider(["search"])
        sel = _make_selector("msg", tools, llm)
        with self.assertRaisesRegex(TypeError, "llm must be an LLMProvider"):
            await sel.process(message="msg", tools=tools, llm="bad")  # type: ignore[arg-type]

    async def test_rejects_non_tool_in_list(self) -> None:
        tools = [StubTool(name="search")]
        llm = StubLLMProvider(["search"])
        sel = _make_selector("msg", tools, llm)
        with self.assertRaisesRegex(TypeError, r"tools\[0\] must be a Tool"):
            await sel.process(message="msg", tools=["not-a-tool"], llm=llm)  # type: ignore[list-item]

    async def test_rejects_empty_tools(self) -> None:
        tools = [StubTool(name="search")]
        llm = StubLLMProvider(["search"])
        sel = _make_selector("msg", tools, llm)
        with self.assertRaisesRegex(ValueError, "tools must not be empty"):
            await sel.process(message="msg", tools=[], llm=llm)


class TestToolSelectorHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_returns_selected_tool_names(self) -> None:
        tools = [StubTool(name="web_search"), StubTool(name="calculator")]
        llm = StubLLMProvider(["web_search"])
        sel = _make_selector("search the web for news", tools, llm)
        selected = await sel.process(message="search the web for news", tools=tools, llm=llm)
        assert selected == ["web_search"]

    async def test_returns_empty_when_none_selected(self) -> None:
        tools = [StubTool(name="web_search")]
        llm = StubLLMProvider(["NONE"])
        sel = _make_selector("just say hello", tools, llm)
        selected = await sel.process(message="just say hello", tools=tools, llm=llm)
        assert selected == []

    async def test_filters_unknown_tool_names_from_llm(self) -> None:
        tools = [StubTool(name="valid_tool")]
        llm = StubLLMProvider(["invalid_tool\nvalid_tool"])
        sel = _make_selector("do something", tools, llm)
        selected = await sel.process(message="do something", tools=tools, llm=llm)
        assert selected == ["valid_tool"]
