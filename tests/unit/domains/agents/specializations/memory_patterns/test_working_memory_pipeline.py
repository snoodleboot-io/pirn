"""Tests for :class:`WorkingMemoryPipeline`."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from typing import Any

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.memory_store import MemoryStore
from pirn.domains.agents.specializations.memory_patterns.working_memory_pipeline import (
    WorkingMemoryPipeline,
)
from pirn.domains.agents.types.agent_message import AgentMessage
from pirn.tapestry import Tapestry


class WindowMemoryStore(MemoryStore):
    """Stores AgentMessage tuples in-process so window read/write round-trips."""

    def __init__(self) -> None:
        self.entries: dict[str, dict[str, Any]] = {}

    async def store(self, key: str, value: Mapping[str, Any]) -> None:
        self.entries[key] = dict(value)

    async def retrieve(self, key: str) -> Mapping[str, Any] | None:
        return self.entries.get(key)

    async def search(
        self,
        query: str,
        *,
        top_k: int = 10,
    ) -> AsyncIterator[Mapping[str, Any]]:
        async def _aiter() -> AsyncIterator[Mapping[str, Any]]:
            if False:
                yield {}

        return _aiter()

    async def forget(self, key: str) -> None:
        self.entries.pop(key, None)

    async def close(self) -> None:
        return None


@pytest.mark.asyncio
class TestWorkingMemoryPipelineConstruction:
    async def test_rejects_zero_max_size(self) -> None:
        store = WindowMemoryStore()
        with pytest.raises(ValueError, match="max_size"):
            with Tapestry():
                WorkingMemoryPipeline(
                    new_message=AgentMessage(role="user", content="hi"),
                    session_id="s1",
                    store=store,
                    max_size=0,
                    _config=KnotConfig(id="win"),
                )


@pytest.mark.asyncio
class TestWorkingMemoryPipelineHappyPath:
    async def test_appends_and_trims_window(self) -> None:
        store = WindowMemoryStore()
        store.entries["working:s1"] = {
            "session_id": "s1",
            "messages": [
                AgentMessage(role="user", content=f"msg-{i}")
                for i in range(3)
            ],
        }
        with Tapestry() as t:
            WorkingMemoryPipeline(
                new_message=AgentMessage(role="user", content="msg-3"),
                session_id="s1",
                store=store,
                max_size=3,
                _config=KnotConfig(id="win"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        window = result.outputs["win"]
        assert isinstance(window, tuple)
        assert len(window) == 3
        assert window[0].content == "msg-1"
        assert window[1].content == "msg-2"
        assert window[2].content == "msg-3"
        # Stored back into the same key with trimmed payload.
        stored = store.entries["working:s1"]
        assert len(stored["messages"]) == 3
