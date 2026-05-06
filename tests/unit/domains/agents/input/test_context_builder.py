"""Unit tests for :class:`ContextBuilder`."""

from __future__ import annotations
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.domains.agents.input.context_builder import ContextBuilder
from pirn.domains.agents.types.agent_context import AgentContext
from pirn.domains.agents.types.agent_message import AgentMessage
from pirn.tapestry import Tapestry


def _make_knot() -> ContextBuilder:
    @knot
    async def _m() -> tuple:
        return ()

    with Tapestry():
        upstream = _m(_config=KnotConfig(id="m"))
        return ContextBuilder(messages=upstream, _config=KnotConfig(id="ctx"))


_MESSAGES = (
    AgentMessage(role="user", content="hi"),
    AgentMessage(role="assistant", content="ok"),
)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_builds_context_without_system_prompt(self) -> None:
        k = _make_knot()
        ctx: AgentContext = await k.process(messages=_MESSAGES, system_prompt=None)
        assert isinstance(ctx, AgentContext)
        assert len(ctx.messages) == 2

    async def test_prepends_system_prompt(self) -> None:
        k = _make_knot()
        ctx: AgentContext = await k.process(messages=_MESSAGES, system_prompt="Be helpful.")
        assert ctx.messages[0].role == "system"
        assert ctx.messages[0].content == "Be helpful."
        assert len(ctx.messages) == 3

    async def test_rejects_non_string_system_prompt(self) -> None:
        k = _make_knot()
        with self.assertRaisesRegex(TypeError, "system_prompt"):
            await k.process(
                messages=(),
                system_prompt=42,  # type: ignore[arg-type]
            )

    async def test_rejects_empty_system_prompt(self) -> None:
        k = _make_knot()
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await k.process(messages=(), system_prompt="")

    async def test_rejects_non_sequence_messages(self) -> None:
        k = _make_knot()
        with self.assertRaises(TypeError):
            await k.process(
                messages="not a sequence",  # type: ignore[arg-type]
                system_prompt=None,
            )
