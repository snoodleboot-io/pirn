"""Unit tests for :class:`StreamingLLMCall`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.agents.generation.streaming_llm_call import StreamingLLMCall
from pirn.domains.agents.types.agent_context import AgentContext
from pirn.domains.agents.types.agent_message import AgentMessage
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.conftest import StubLLMProvider


@knot
async def emit_context() -> AgentContext:
    return AgentContext(
        messages=(AgentMessage(role="user", content="stream"),),
    )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_async_iterator(self) -> None:
        llm = StubLLMProvider(responses=["a", "b", "c"])
        with Tapestry() as t:
            ctx = emit_context(
                _config=KnotConfig(id="ctx", validate_io=False),
            )
            StreamingLLMCall(
                context=ctx,
                llm=llm,
                _config=KnotConfig(id="s", validate_io=False),
            )
        result = await t.run(RunRequest())
        stream = result.outputs["s"]
        chunks: list[str] = []
        async for chunk in stream:
            chunks.append(chunk["content"])
        assert chunks == ["a", "b", "c"]


class TestConstruction(unittest.TestCase):
    def test_requires_llm_provider(self) -> None:
        @knot
        async def empty() -> AgentContext:
            return AgentContext(messages=())

        with Tapestry():
            ctx = empty(_config=KnotConfig(id="ctx"))
            with self.assertRaisesRegex(TypeError, "LLMProvider"):
                StreamingLLMCall(
                    context=ctx,
                    llm="bad",  # type: ignore[arg-type]
                    _config=KnotConfig(id="s"),
                )
