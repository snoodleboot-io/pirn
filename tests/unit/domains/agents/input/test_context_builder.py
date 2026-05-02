"""Unit tests for :class:`ContextBuilder`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.agents.input.context_builder import ContextBuilder
from pirn.domains.agents.types.agent_context import AgentContext
from pirn.domains.agents.types.agent_message import AgentMessage
from pirn.tapestry import Tapestry


@knot
async def emit_messages() -> tuple[AgentMessage, ...]:
    return (
        AgentMessage(role="user", content="hi"),
        AgentMessage(role="assistant", content="ok"),
    )


@pytest.mark.asyncio
class TestProcess:
    async def test_builds_context_without_system_prompt(self) -> None:
        with Tapestry() as t:
            messages = emit_messages(_config=KnotConfig(id="m"))
            ContextBuilder(messages=messages, _config=KnotConfig(id="ctx"))
        result = await t.run(RunRequest())
        ctx: AgentContext = result.outputs["ctx"]
        assert isinstance(ctx, AgentContext)
        assert len(ctx.messages) == 2

    async def test_prepends_system_prompt(self) -> None:
        with Tapestry() as t:
            messages = emit_messages(_config=KnotConfig(id="m"))
            ContextBuilder(
                messages=messages,
                system_prompt="Be helpful.",
                _config=KnotConfig(id="ctx"),
            )
        result = await t.run(RunRequest())
        ctx: AgentContext = result.outputs["ctx"]
        assert ctx.messages[0].role == "system"
        assert ctx.messages[0].content == "Be helpful."
        assert len(ctx.messages) == 3


class TestConstruction:
    def test_rejects_non_string_system_prompt(self) -> None:
        @knot
        async def empty() -> tuple:
            return ()

        with Tapestry():
            messages = empty(_config=KnotConfig(id="empty"))
            with pytest.raises(TypeError, match="system_prompt"):
                ContextBuilder(
                    messages=messages,
                    system_prompt=42,  # type: ignore[arg-type]
                    _config=KnotConfig(id="ctx"),
                )

    def test_rejects_empty_system_prompt(self) -> None:
        @knot
        async def empty() -> tuple:
            return ()

        with Tapestry():
            messages = empty(_config=KnotConfig(id="empty"))
            with pytest.raises(ValueError, match="non-empty"):
                ContextBuilder(
                    messages=messages,
                    system_prompt="",
                    _config=KnotConfig(id="ctx"),
                )
