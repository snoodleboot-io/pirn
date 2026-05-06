"""Tests for :class:`EpisodicMemoryPipeline`."""

from __future__ import annotations

import unittest
from collections.abc import AsyncIterator, Mapping
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.memory_store import MemoryStore
from pirn.domains.agents.specializations.memory_patterns.episodic_memory_pipeline import (
    EpisodicMemoryPipeline,
)
from pirn.domains.agents.types.agent_message import AgentMessage
from pirn.tapestry import Tapestry


class RecordingMemoryStore(MemoryStore):
    """In-memory store that records writes for assertion."""

    def __init__(self) -> None:
        self.writes: dict[str, Mapping[str, Any]] = {}

    async def store(self, key: str, value: Mapping[str, Any]) -> None:
        self.writes[key] = dict(value)

    async def retrieve(self, key: str) -> Mapping[str, Any] | None:
        return self.writes.get(key)

    async def search(self, query: str, *, top_k: int = 10) -> AsyncIterator[Mapping[str, Any]]:
        async def _aiter() -> AsyncIterator[Mapping[str, Any]]:
            if False:
                yield {}

        return _aiter()

    async def forget(self, key: str) -> None:
        self.writes.pop(key, None)

    async def close(self) -> None:
        return None


def _make_knot(store: RecordingMemoryStore) -> EpisodicMemoryPipeline:
    with Tapestry():
        return EpisodicMemoryPipeline(
            messages=(),
            session_id="s0",
            store=store,
            _config=KnotConfig(id="ep"),
        )


class TestEpisodicMemoryPipelineProcess(unittest.IsolatedAsyncioTestCase):
    async def test_writes_episode_under_session_keyed_path(self) -> None:
        store = RecordingMemoryStore()
        with Tapestry() as t:
            EpisodicMemoryPipeline(
                messages=(
                    AgentMessage(role="user", content="hello"),
                    AgentMessage(role="assistant", content="hi back"),
                ),
                session_id="conv-42",
                store=store,
                _config=KnotConfig(id="ep"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        key = result.outputs["ep"]
        assert isinstance(key, str)
        assert key.startswith("episode:conv-42:")
        assert key in store.writes
        payload = store.writes[key]
        assert payload["session_id"] == "conv-42"
        assert len(payload["messages"]) == 2

    async def test_rejects_non_memory_store(self) -> None:
        store = RecordingMemoryStore()
        k = _make_knot(store)
        with self.assertRaises(TypeError):
            await k.process(messages=(), session_id="s1", store="bad")  # type: ignore[arg-type]

    async def test_rejects_empty_session_id(self) -> None:
        store = RecordingMemoryStore()
        k = _make_knot(store)
        with self.assertRaises(ValueError):
            await k.process(messages=(), session_id="", store=store)
