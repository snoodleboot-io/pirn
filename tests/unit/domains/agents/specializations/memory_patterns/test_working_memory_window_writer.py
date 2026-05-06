"""Unit tests for :class:`WorkingMemoryWindowWriter`."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.specializations.memory_patterns.working_memory_window_writer import (
    WorkingMemoryWindowWriter,
)
from pirn.domains.agents.types.agent_message import AgentMessage
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import StubMemoryStore


class _TrackingStore(StubMemoryStore):
    def __init__(self, existing_messages=None):
        super().__init__(hits=[])
        self._existing = existing_messages
        self.stored: dict[str, Any] = {}

    async def retrieve(self, key: str) -> Mapping[str, Any] | None:
        if self._existing is not None:
            return {"messages": self._existing}
        return None

    async def store(self, key: str, value: Mapping[str, Any]) -> None:
        self.stored[key] = dict(value)


def _msg(content: str) -> AgentMessage:
    return AgentMessage(role="user", content=content)


def _make_knot() -> WorkingMemoryWindowWriter:
    with Tapestry():
        return WorkingMemoryWindowWriter(
            new_message=_msg("hi"),
            session_id="s0",
            store=_TrackingStore(),
            max_size=10,
            _config=KnotConfig(id="wmww"),
        )


class TestWorkingMemoryWindowWriterProcess(unittest.IsolatedAsyncioTestCase):
    async def test_appends_message_to_empty_window(self) -> None:
        k = _make_knot()
        store = _TrackingStore()
        msg = _msg("first message")
        window = await k.process(new_message=msg, session_id="s1", store=store, max_size=10)
        assert len(window) == 1
        assert window[0].content == "first message"

    async def test_trims_to_max_size(self) -> None:
        k = _make_knot()
        existing = [_msg(f"old-{i}") for i in range(5)]
        store = _TrackingStore(existing_messages=existing)
        window = await k.process(new_message=_msg("new"), session_id="s1", store=store, max_size=3)
        assert len(window) == 3
        assert window[-1].content == "new"

    async def test_rejects_non_agent_message(self) -> None:
        k = _make_knot()
        store = _TrackingStore()
        with self.assertRaises(TypeError):
            await k.process(new_message="not-a-message", session_id="s1", store=store, max_size=5)  # type: ignore[arg-type]

    async def test_rejects_non_memory_store(self) -> None:
        k = _make_knot()
        with self.assertRaises(TypeError):
            await k.process(new_message=_msg("hi"), session_id="s1", store="bad", max_size=5)  # type: ignore[arg-type]

    async def test_rejects_empty_session_id(self) -> None:
        k = _make_knot()
        store = _TrackingStore()
        with self.assertRaises(ValueError):
            await k.process(new_message=_msg("hi"), session_id="", store=store, max_size=5)

    async def test_rejects_non_positive_max_size(self) -> None:
        k = _make_knot()
        store = _TrackingStore()
        with self.assertRaises(ValueError):
            await k.process(new_message=_msg("hi"), session_id="s1", store=store, max_size=0)
