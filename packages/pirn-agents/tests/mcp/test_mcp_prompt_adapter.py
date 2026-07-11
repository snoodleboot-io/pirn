"""Tests for the MCP prompt adapter + template (S4 / PIR-161, PIR-200, PIR-204).

Prompt definitions convert into reusable :class:`McpPromptTemplate`s; rendering
substitutes arguments into message bodies, validates argument types via
``isinstance``, and enforces required arguments.
"""

from __future__ import annotations

import pytest

from pirn_agents.mcp.mcp_client import McpClient
from pirn_agents.mcp.mcp_error import McpError
from pirn_agents.mcp.mcp_prompt_adapter import McpPromptAdapter
from pirn_agents.mcp.mcp_prompt_template import McpPromptTemplate
from pirn_agents.types.agent_message import AgentMessage
from tests.mcp.stub_mcp import StubMcpTransport


async def _template(name: str = "greet") -> McpPromptTemplate:
    client = McpClient(StubMcpTransport())
    await client.open()
    return await McpPromptAdapter(client=client).build_template(name)


async def test_build_template_captures_required_arguments() -> None:
    template = await _template()

    assert template.name == "greet"
    assert template.description == "Greet a person in a language."
    assert template.required_arguments == frozenset({"name"})


async def test_render_substitutes_arguments() -> None:
    template = await _template()

    messages = _render(template, {"name": "Ada", "lang": "English"})

    assert all(isinstance(m, AgentMessage) for m in messages)
    assert messages[0].role == "system"
    assert messages[0].content == "Respond in English."
    assert messages[1].role == "user"
    assert messages[1].content == "Hello Ada!"


async def test_render_reusable_across_arguments() -> None:
    template = await _template()

    first = _render(template, {"name": "Ada", "lang": "French"})
    second = _render(template, {"name": "Bob", "lang": "German"})

    assert first[1].content == "Hello Ada!"
    assert second[1].content == "Hello Bob!"


async def test_render_missing_required_raises() -> None:
    template = await _template()

    with pytest.raises(ValueError):
        template.render({"lang": "English"})


async def test_render_non_string_argument_raises_type_error() -> None:
    template = await _template()

    with pytest.raises(TypeError):
        template.render({"name": 123})  # type: ignore[dict-item]


async def test_render_non_mapping_raises_type_error() -> None:
    template = await _template()

    with pytest.raises(TypeError):
        template.render("nope")  # type: ignore[arg-type]


async def test_build_template_unknown_prompt_raises() -> None:
    client = McpClient(StubMcpTransport())
    await client.open()

    with pytest.raises(McpError):
        await McpPromptAdapter(client=client).build_template("does-not-exist")


async def test_list_prompts_surfaces_descriptors() -> None:
    client = McpClient(StubMcpTransport())
    await client.open()

    prompts = await McpPromptAdapter(client=client).list_prompts()

    assert [p["name"] for p in prompts] == ["greet"]


def _render(template: McpPromptTemplate, arguments: dict[str, str]) -> list[AgentMessage]:
    """Render a template (sync helper; ``render`` itself is synchronous)."""
    return template.render(arguments)
