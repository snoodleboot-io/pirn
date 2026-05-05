"""Tests for :class:`ProceduralMemoryPipeline`."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from typing import Any
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.memory_store import MemoryStore
from pirn.domains.agents.specializations.memory_patterns.procedural_memory_pipeline import (
    ProceduralMemoryPipeline,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry


class RecordingMemoryStore(MemoryStore):
    def __init__(self) -> None:
        self.writes: dict[str, Mapping[str, Any]] = {}

    async def store(self, key: str, value: Mapping[str, Any]) -> None:
        self.writes[key] = dict(value)

    async def retrieve(self, key: str) -> Mapping[str, Any] | None:
        return self.writes.get(key)

    async def search(self, query: str, *, top_k: int = 10,) -> AsyncIterator[Mapping[str, Any]]:
        async def _aiter() -> AsyncIterator[Mapping[str, Any]]:
            if False:
                yield {}

        return _aiter()

    async def forget(self, key: str) -> None:
        self.writes.pop(key, None)

    async def close(self) -> None:
        return None


class TestProceduralMemoryPipelineConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_memory_store(self) -> None:
        response = AgentResponse(content="done", finish_reason="stop")
        with self.assertRaisesRegex(TypeError, "store must be a MemoryStore"):
            with Tapestry():
                ProceduralMemoryPipeline(
                    agent_response=response,
                    task_description="how to greet",
                    store="not-a-store",  # type: ignore[arg-type]
                    _config=KnotConfig(id="proc"),
                )


class TestProceduralMemoryPipelineHappyPath(unittest.IsolatedAsyncioTestCase):
    async def test_writes_procedure_under_procedure_prefix(self) -> None:
        store = RecordingMemoryStore()
        response = AgentResponse(
            content="say 'hello'",
            finish_reason="stop",
        )
        with Tapestry() as t:
            ProceduralMemoryPipeline(
                agent_response=response,
                task_description="how to greet a user",
                store=store,
                _config=KnotConfig(id="proc"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        key = result.outputs["proc"]
        assert isinstance(key, str)
        assert key.startswith("procedure:")
        payload = store.writes[key]
        assert payload["task"] == "how to greet a user"
        assert payload["response"] == "say 'hello'"
        assert payload["finish_reason"] == "stop"
