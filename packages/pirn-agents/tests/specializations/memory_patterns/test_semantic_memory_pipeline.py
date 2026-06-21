"""Tests for :class:`SemanticMemoryPipeline`."""

from __future__ import annotations

import unittest
from collections.abc import AsyncIterator, Mapping
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn_agents.memory_store import MemoryStore
from pirn_agents.specializations.memory_patterns.semantic_memory_pipeline import (
    SemanticMemoryPipeline,
)
from pirn_agents.types.agent_message import AgentMessage
from pirn.tapestry import Tapestry

from tests.specializations.conftest import StubLLMProvider


class RecordingMemoryStore(MemoryStore):
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


def _make_knot(store: RecordingMemoryStore, llm: StubLLMProvider) -> SemanticMemoryPipeline:
    with Tapestry():
        return SemanticMemoryPipeline(
            messages=(),
            llm=llm,
            store=store,
            _config=KnotConfig(id="sem"),
        )


class TestSemanticMemoryPipelineProcess(unittest.IsolatedAsyncioTestCase):
    async def test_extracts_facts_and_returns_count(self) -> None:
        store = RecordingMemoryStore()
        llm = StubLLMProvider(
            [
                "- water freezes at 0C\n- water boils at 100C\n- ice floats"
            ]
        )
        with Tapestry() as t:
            SemanticMemoryPipeline(
                messages=(
                    AgentMessage(role="user", content="give physics facts"),
                ),
                llm=llm,
                store=store,
                _config=KnotConfig(id="sem"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        count = result.outputs["sem"]
        assert count == 3
        assert len(store.writes) == 3
        for key, payload in store.writes.items():
            assert key.startswith("semantic:")
            assert isinstance(payload["fact"], str)

    async def test_rejects_non_llm_provider(self) -> None:
        store = RecordingMemoryStore()
        k = _make_knot(store, StubLLMProvider([]))
        with self.assertRaises(TypeError):
            await k.process(
                messages=(),
                llm="bad",  # type: ignore[arg-type]
                store=store,
            )

    async def test_rejects_empty_extraction_prompt(self) -> None:
        store = RecordingMemoryStore()
        k = _make_knot(store, StubLLMProvider([]))
        with self.assertRaises(ValueError):
            await k.process(
                messages=(),
                llm=StubLLMProvider([]),
                store=store,
                fact_extraction_prompt="",
            )
