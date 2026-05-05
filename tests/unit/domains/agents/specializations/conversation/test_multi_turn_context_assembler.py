"""Tests for :class:`MultiTurnContextAssembler`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.specializations.conversation.multi_turn_context_assembler import (
    MultiTurnContextAssembler,
)
from pirn.domains.agents.types.agent_message import AgentMessage
from pirn.tapestry import Tapestry


def _make_message(role: str, content: str) -> AgentMessage:
    return AgentMessage(role=role, content=content)


class TestMultiTurnContextAssemblerConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_zero_max_turns(self) -> None:
        with self.assertRaisesRegex(ValueError, "max_turns must be a positive int"):
            with Tapestry():
                MultiTurnContextAssembler(
                    messages=[],
                    max_turns=0,
                    max_tokens=1000,
                    _config=KnotConfig(id="mtca"),
                )

    async def test_rejects_zero_max_tokens(self) -> None:
        with self.assertRaisesRegex(ValueError, "max_tokens must be a positive int"):
            with Tapestry():
                MultiTurnContextAssembler(
                    messages=[],
                    max_turns=5,
                    max_tokens=0,
                    _config=KnotConfig(id="mtca"),
                )


class TestMultiTurnContextAssemblerProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_all_messages_within_limits(self) -> None:
        messages = [
            _make_message("user", "hello"),
            _make_message("assistant", "hi"),
        ]
        with Tapestry() as t:
            MultiTurnContextAssembler(
                messages=messages,
                max_turns=10,
                max_tokens=1000,
                _config=KnotConfig(id="mtca"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        assembled = result.outputs["mtca"]
        assert len(assembled) == 2
        assert assembled[0] == {"role": "user", "content": "hello"}
        assert assembled[1] == {"role": "assistant", "content": "hi"}

    async def test_respects_max_turns(self) -> None:
        messages = [_make_message("user", f"msg{i}") for i in range(5)]
        with Tapestry() as t:
            MultiTurnContextAssembler(
                messages=messages,
                max_turns=2,
                max_tokens=10000,
                _config=KnotConfig(id="mtca"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        assembled = result.outputs["mtca"]
        assert len(assembled) == 2
        assert assembled[-1]["content"] == "msg4"

    async def test_respects_max_tokens(self) -> None:
        messages = [
            _make_message("user", "a" * 100),
            _make_message("assistant", "b" * 100),
            _make_message("user", "c" * 100),
        ]
        with Tapestry() as t:
            MultiTurnContextAssembler(
                messages=messages,
                max_turns=10,
                max_tokens=150,
                _config=KnotConfig(id="mtca"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        assembled = result.outputs["mtca"]
        assert len(assembled) == 1
        assert assembled[0]["content"] == "c" * 100

    async def test_returns_empty_for_empty_messages(self) -> None:
        with Tapestry() as t:
            MultiTurnContextAssembler(
                messages=[],
                max_turns=5,
                max_tokens=1000,
                _config=KnotConfig(id="mtca"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        assert result.outputs["mtca"] == []
