"""Tests for :class:`ToolSelector`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.tool_use.tool_selector import ToolSelector
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import (
    StubLLMProvider,
    StubTool,
)


class TestToolSelectorConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_llm_provider(self) -> None:
        tools = [StubTool(name="search")]
        with self.assertRaisesRegex(TypeError, "llm must be an LLMProvider"):
            with Tapestry():
                ToolSelector(
                    message="msg",
                    tools=tools,
                    llm="bad",  # type: ignore[arg-type]
                    _config=KnotConfig(id="sel"),
                )

    async def test_rejects_non_tool_in_list(self) -> None:
        llm = StubLLMProvider(["search"])
        with self.assertRaisesRegex(TypeError, r"tools\[0\] must be a Tool"):
            with Tapestry():
                ToolSelector(
                    message="msg",
                    tools=["not-a-tool"],  # type: ignore[list-item]
                    llm=llm,
                    _config=KnotConfig(id="sel"),
                )

    async def test_rejects_empty_tools(self) -> None:
        llm = StubLLMProvider(["search"])
        with self.assertRaisesRegex(ValueError, "tools must not be empty"):
            with Tapestry():
                ToolSelector(
                    message="msg",
                    tools=[],
                    llm=llm,
                    _config=KnotConfig(id="sel"),
                )


class TestToolSelectorHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_returns_selected_tool_names(self) -> None:
        tools = [StubTool(name="web_search"), StubTool(name="calculator")]
        llm = StubLLMProvider(["web_search"])
        with Tapestry() as t:
            ToolSelector(
                message="search the web for news",
                tools=tools,
                llm=llm,
                _config=KnotConfig(id="sel"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        selected = result.outputs["sel"]
        assert selected == ["web_search"]

    async def test_returns_empty_when_none_selected(self) -> None:
        tools = [StubTool(name="web_search")]
        llm = StubLLMProvider(["NONE"])
        with Tapestry() as t:
            ToolSelector(
                message="just say hello",
                tools=tools,
                llm=llm,
                _config=KnotConfig(id="sel"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        selected = result.outputs["sel"]
        assert selected == []

    async def test_filters_unknown_tool_names_from_llm(self) -> None:
        tools = [StubTool(name="valid_tool")]
        llm = StubLLMProvider(["invalid_tool\nvalid_tool"])
        with Tapestry() as t:
            ToolSelector(
                message="do something",
                tools=tools,
                llm=llm,
                _config=KnotConfig(id="sel"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        selected = result.outputs["sel"]
        assert selected == ["valid_tool"]
