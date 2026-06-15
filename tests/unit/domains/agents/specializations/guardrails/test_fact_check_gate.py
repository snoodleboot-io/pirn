"""Tests for :class:`FactCheckGate`."""

from __future__ import annotations

import unittest
from collections.abc import AsyncIterator, Mapping
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn_agents.memory_store import MemoryStore
from pirn_agents.specializations.guardrails.fact_check_gate import (
    FactCheckGate,
)
from pirn_agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry

from tests.unit.domains.agents.specializations.conftest import StubLLMProvider


class ScriptedSearchStore(MemoryStore):
    """Memory store whose ``search`` returns hits keyed by query substring."""

    def __init__(self, supported_substrings: tuple[str, ...]) -> None:
        self._supported = supported_substrings
        self.queries: list[str] = []

    async def store(self, key: str, value: Mapping[str, Any]) -> None:
        return None

    async def retrieve(self, key: str) -> Mapping[str, Any] | None:
        return None

    async def search(self, query: str, *, top_k: int = 10) -> AsyncIterator[Mapping[str, Any]]:
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


def _make_knot(llm: StubLLMProvider, store: MemoryStore) -> FactCheckGate:
    with Tapestry():
        return FactCheckGate(
            response=AgentResponse(content="ok", finish_reason="stop"),
            store=store,
            llm=llm,
            _config=KnotConfig(id="fc"),
        )


class TestFactCheckGateProcess(unittest.IsolatedAsyncioTestCase):
    async def test_process_appends_warning_for_unverified_claims(self) -> None:
        llm = StubLLMProvider(["- earth orbits sun\n- moon is made of cheese"])
        store = ScriptedSearchStore(supported_substrings=("earth orbits sun",))
        response = AgentResponse(
            content="Earth orbits the sun. The moon is made of cheese.",
            finish_reason="stop",
        )
        with Tapestry() as t:
            FactCheckGate(response=response, store=store, llm=llm, _config=KnotConfig(id="fc"))
        run = await t.run(RunRequest())
        assert run.succeeded
        result = run.outputs["fc"]
        assert isinstance(result, AgentResponse)
        assert "Unverified claims" in result.content
        assert "moon is made of cheese" in result.content

    async def test_process_returns_original_when_all_verified(self) -> None:
        llm = StubLLMProvider(["- earth orbits sun"])
        store = ScriptedSearchStore(supported_substrings=("earth orbits sun",))
        response = AgentResponse(content="Earth orbits the sun.", finish_reason="stop")
        with Tapestry() as t:
            FactCheckGate(response=response, store=store, llm=llm, _config=KnotConfig(id="fc"))
        run = await t.run(RunRequest())
        assert run.succeeded
        result = run.outputs["fc"]
        assert "Unverified" not in result.content


class TestFactCheckGateHappyPath(unittest.IsolatedAsyncioTestCase):
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
