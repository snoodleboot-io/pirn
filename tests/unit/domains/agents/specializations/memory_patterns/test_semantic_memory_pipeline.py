"""Tests for :class:`SemanticMemoryPipeline`."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from typing import Any

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.memory_store import MemoryStore
from pirn.domains.agents.specializations.memory_patterns.semantic_memory_pipeline import (
    SemanticMemoryPipeline,
)
from pirn.domains.agents.types.agent_message import AgentMessage
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import StubLLMProvider


class RecordingMemoryStore(MemoryStore):
    def __init__(self) -> None:
        self.writes: dict[str, Mapping[str, Any]] = {}

    async def store(self, key: str, value: Mapping[str, Any]) -> None:
        self.writes[key] = dict(value)

    async def retrieve(self, key: str) -> Mapping[str, Any] | None:
        return self.writes.get(key)

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
        self.writes.pop(key, None)

    async def close(self) -> None:
        return None


@pytest.mark.asyncio
class TestSemanticMemoryPipelineConstruction:
    async def test_rejects_non_llm_provider(self) -> None:
        store = RecordingMemoryStore()
        with pytest.raises(TypeError, match="llm must be an LLMProvider"):
            with Tapestry():
                SemanticMemoryPipeline(
                    messages=(AgentMessage(role="user", content="hi"),),
                    llm="not-a-provider",  # type: ignore[arg-type]
                    store=store,
                    _config=KnotConfig(id="sem"),
                )

    async def test_rejects_empty_extraction_prompt(self) -> None:
        store = RecordingMemoryStore()
        llm = StubLLMProvider(["fact"])
        with pytest.raises(
            ValueError, match="fact_extraction_prompt"
        ):
            with Tapestry():
                SemanticMemoryPipeline(
                    messages=(AgentMessage(role="user", content="hi"),),
                    llm=llm,
                    store=store,
                    fact_extraction_prompt="",
                    _config=KnotConfig(id="sem"),
                )


@pytest.mark.asyncio
class TestSemanticMemoryPipelineHappyPath:
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
