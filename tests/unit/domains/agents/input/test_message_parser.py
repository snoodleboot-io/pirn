"""Unit tests for :class:`MessageParser`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.agents.input.message_parser import MessageParser
from pirn.domains.agents.types.agent_message import AgentMessage
from pirn.tapestry import Tapestry


@knot
async def emit_string() -> str:
    return "hello world"


@knot
async def emit_mapping() -> dict[str, str]:
    return {"role": "assistant", "content": "hi there"}


@knot
async def emit_messages() -> tuple:
    return (
        {"role": "user", "content": "u"},
        AgentMessage(role="assistant", content="a"),
        "plain string",
    )


@pytest.mark.asyncio
class TestProcess:
    async def test_string_becomes_user_message(self) -> None:
        with Tapestry() as t:
            raw = emit_string(_config=KnotConfig(id="raw"))
            MessageParser(raw_input=raw, _config=KnotConfig(id="p"))
        result = await t.run(RunRequest())
        out = result.outputs["p"]
        assert isinstance(out, tuple) and len(out) == 1
        assert out[0].role == "user"
        assert out[0].content == "hello world"

    async def test_mapping_with_role(self) -> None:
        with Tapestry() as t:
            raw = emit_mapping(_config=KnotConfig(id="raw"))
            MessageParser(raw_input=raw, _config=KnotConfig(id="p"))
        result = await t.run(RunRequest())
        out = result.outputs["p"]
        assert out[0].role == "assistant"
        assert out[0].content == "hi there"

    async def test_sequence_of_mixed_items(self) -> None:
        with Tapestry() as t:
            raw = emit_messages(_config=KnotConfig(id="raw"))
            MessageParser(raw_input=raw, _config=KnotConfig(id="p"))
        result = await t.run(RunRequest())
        out = result.outputs["p"]
        assert len(out) == 3
        assert out[0].role == "user"
        assert out[1].role == "assistant"
        assert out[2].role == "user"
        assert out[2].content == "plain string"


class TestConstruction:
    def test_requires_raw_input(self) -> None:
        with pytest.raises(TypeError, match="raw_input"):
            MessageParser(_config=KnotConfig(id="p"))  # type: ignore[call-arg]
