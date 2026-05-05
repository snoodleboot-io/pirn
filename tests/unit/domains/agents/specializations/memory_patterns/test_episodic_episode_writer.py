"""Unit tests for :class:`EpisodicEpisodeWriter`."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
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


class TestEpisodicEpisodeWriterConstruction(unittest.TestCase):
    def test_rejects_non_memory_store(self) -> None:
        with self.assertRaisesRegex(TypeError, "MemoryStore"):
            with Tapestry():
                EpisodicEpisodeWriter(
                    messages=[],
                    session_id="s1",
                    store="bad",  # type: ignore[arg-type]
                    _config=KnotConfig(id="eew"),
                )

    def test_rejects_empty_session_id(self) -> None:
        with self.assertRaisesRegex(ValueError, "session_id"):
            with Tapestry():
                EpisodicEpisodeWriter(
                    messages=[],
                    session_id="",
                    store=StubMemoryStore(hits=[]),
                    _config=KnotConfig(id="eew"),
                )


class TestEpisodicEpisodeWriterProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_key_with_session_id(self) -> None:
        store = _TrackingStore()
        with Tapestry() as t:
            EpisodicEpisodeWriter(
                messages=[_msg("hello")],
                session_id="sess-1",
                store=store,
                _config=KnotConfig(id="eew"),
            )
        result = await t.run(RunRequest())
        key = result.outputs["eew"]
        assert "sess-1" in key
        assert key.startswith("episode:")

    async def test_stores_payload_with_messages(self) -> None:
        store = _TrackingStore()
        msgs = [_msg("a"), _msg("b", role="assistant")]
        with Tapestry() as t:
            EpisodicEpisodeWriter(
                messages=msgs,
                session_id="sess-2",
                store=store,
                _config=KnotConfig(id="eew"),
            )
        result = await t.run(RunRequest())
        key = result.outputs["eew"]
        assert key in store.stored
        assert len(store.stored[key]["messages"]) == 2

    async def test_rejects_non_agent_message(self) -> None:
        store = _TrackingStore()
        with Tapestry():
            with self.assertRaises(TypeError):
                EpisodicEpisodeWriter(
                    messages=["not-a-message"],  # type: ignore[list-item]
                    session_id="sess-3",
                    store=store,
                    _config=KnotConfig(id="eew"),
                )
