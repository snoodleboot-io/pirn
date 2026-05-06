"""Unit tests for :class:`EpisodicEpisodeWriter`."""

from __future__ import annotations

import unittest
from collections.abc import Mapping
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.specializations.memory_patterns.episodic_episode_writer import (
    EpisodicEpisodeWriter,
)
from pirn.domains.agents.types.agent_message import AgentMessage
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import StubMemoryStore


class _TrackingStore(StubMemoryStore):
    def __init__(self):
        super().__init__(hits=[])
        self.stored: dict[str, Any] = {}

    async def store(self, key: str, value: Mapping[str, Any]) -> None:
        self.stored[key] = dict(value)


def _msg(content: str, role: str = "user") -> AgentMessage:
    return AgentMessage(role=role, content=content)


def _make_knot() -> EpisodicEpisodeWriter:
    with Tapestry():
        return EpisodicEpisodeWriter(
            messages=[],
            session_id="s0",
            store=_TrackingStore(),
            _config=KnotConfig(id="eew"),
        )


class TestEpisodicEpisodeWriterProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_key_with_session_id(self) -> None:
        k = _make_knot()
        store = _TrackingStore()
        key = await k.process(messages=[_msg("hello")], session_id="sess-1", store=store)
        assert "sess-1" in key
        assert key.startswith("episode:")

    async def test_stores_payload_with_messages(self) -> None:
        k = _make_knot()
        store = _TrackingStore()
        msgs = [_msg("a"), _msg("b", role="assistant")]
        key = await k.process(messages=msgs, session_id="sess-2", store=store)
        assert key in store.stored
        assert len(store.stored[key]["messages"]) == 2

    async def test_rejects_non_agent_message(self) -> None:
        k = _make_knot()
        store = _TrackingStore()
        with self.assertRaises(TypeError):
            await k.process(messages=["not-a-message"], session_id="s", store=store)  # type: ignore[list-item]

    async def test_rejects_non_memory_store(self) -> None:
        k = _make_knot()
        with self.assertRaises(TypeError):
            await k.process(messages=[], session_id="s", store="bad")  # type: ignore[arg-type]

    async def test_rejects_empty_session_id(self) -> None:
        k = _make_knot()
        store = _TrackingStore()
        with self.assertRaises(ValueError):
            await k.process(messages=[], session_id="", store=store)
