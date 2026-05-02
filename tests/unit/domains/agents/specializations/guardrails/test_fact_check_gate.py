"""Tests for :class:`FactCheckGate`."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from typing import Any

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.memory_store import MemoryStore
from pirn.domains.agents.specializations.guardrails.fact_check_gate import (
    FactCheckGate,
)
from pirn.domains.agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry
from tests.unit.domains.agents.specializations.conftest import StubLLMProvider


class ScriptedSearchStore(MemoryStore):
    """Memory store whose ``search`` returns hits keyed by query substring."""

    def __init__(
        self,
        supported_substrings: tuple[str, ...],
    ) -> None:
        self._supported = supported_substrings
        self.queries: list[str] = []

    async def store(self, key: str, value: Mapping[str, Any]) -> None:
        return None

    async def retrieve(self, key: str) -> Mapping[str, Any] | None:
        return None

    async def search(
        self,
        query: str,
        *,
        top_k: int = 10,
    ) -> AsyncIterator[Mapping[str, Any]]:
        self.queries.append(query)
        supported = self._supported
        has_hit = any(token in query for token in supported)

        async def _aiter() -> AsyncIterator[Mapping[str, Any]]:
            if has_hit:
                yield {"fact": query}

        return _aiter()

    async def forget(self, key: str) -> None:
        return None

    async def close(self) -> None:
        return None


@pytest.mark.asyncio
class TestFactCheckGateConstruction:
    async def test_rejects_non_memory_store(self) -> None:
        llm = StubLLMProvider(["claim"])
        response = AgentResponse(content="ok", finish_reason="stop")
        with pytest.raises(TypeError, match="store must be a MemoryStore"):
            with Tapestry():
                FactCheckGate(
                    response=response,
                    store="not-a-store",  # type: ignore[arg-type]
                    llm=llm,
                    _config=KnotConfig(id="fc"),
                )

    async def test_rejects_non_llm_provider(self) -> None:
        store = ScriptedSearchStore(supported_substrings=())
        response = AgentResponse(content="ok", finish_reason="stop")
        with pytest.raises(TypeError, match="llm must be an LLMProvider"):
            with Tapestry():
                FactCheckGate(
                    response=response,
                    store=store,
                    llm="not-a-provider",  # type: ignore[arg-type]
                    _config=KnotConfig(id="fc"),
                )


@pytest.mark.asyncio
class TestFactCheckGateHappyPath:
    async def test_appends_warning_for_unverified_claims(self) -> None:
        # Two claims: only "earth orbits sun" has support in the store.
        llm = StubLLMProvider(
            ["- earth orbits sun\n- moon is made of cheese"]
        )
        store = ScriptedSearchStore(
            supported_substrings=("earth orbits sun",),
        )
        response = AgentResponse(
            content="Earth orbits the sun. The moon is made of cheese.",
            finish_reason="stop",
        )
        with Tapestry() as t:
            FactCheckGate(
                response=response,
                store=store,
                llm=llm,
                _config=KnotConfig(id="fc"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        verified = result.outputs["fc"]
        assert isinstance(verified, AgentResponse)
        assert "Unverified claims" in verified.content
        assert "moon is made of cheese" in verified.content
        assert "earth orbits sun" not in verified.content.split(
            "Unverified claims:"
        )[1]
