"""Unit tests for :class:`FactClaimVerifier`."""

from __future__ import annotations

import unittest
from collections.abc import AsyncIterator, Mapping
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn_agents.memory_store import MemoryStore
from pirn_agents.specializations.guardrails.fact_claim_verifier import (
    FactClaimVerifier,
)
from pirn_agents.types.agent_response import AgentResponse
from pirn.tapestry import Tapestry


class _HitStore(MemoryStore):
    """Returns one hit for queries containing supported substrings."""

    def __init__(self, supported: tuple[str, ...]) -> None:
        self._supported = supported

    async def store(self, key, value) -> None:
        pass

    async def retrieve(self, key) -> None:
        return None

    async def search(self, query, *, top_k=10) -> AsyncIterator[Mapping[str, Any]]:
        has_hit = any(s in query for s in self._supported)

        async def _aiter():
            if has_hit:
                yield {"fact": query}

        return _aiter()

    async def forget(self, key) -> None:
        pass

    async def close(self) -> None:
        pass


def _make_knot(store: MemoryStore) -> FactClaimVerifier:
    with Tapestry():
        return FactClaimVerifier(
            response=AgentResponse(content="ok", finish_reason="stop"),
            claims=[],
            store=store,
            _config=KnotConfig(id="fcv"),
        )


class TestFactClaimVerifierProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_original_response_when_all_verified(self) -> None:
        store = _HitStore(supported=("water is wet",))
        response = AgentResponse(content="ok", finish_reason="stop")
        k = _make_knot(store)
        out = await k.process(response=response, claims=["water is wet"], store=store)
        assert out.content == "ok"

    async def test_appends_warning_for_unverified_claim(self) -> None:
        store = _HitStore(supported=())  # no hits
        response = AgentResponse(content="The moon is cheese.", finish_reason="stop")
        k = _make_knot(store)
        out = await k.process(response=response, claims=["moon is cheese"], store=store)
        assert "Unverified" in out.content
        assert "moon is cheese" in out.content

    async def test_rejects_non_agent_response(self) -> None:
        store = _HitStore(supported=())
        k = _make_knot(store)
        with self.assertRaises(TypeError):
            await k.process(response="not-a-response", claims=[], store=store)  # type: ignore[arg-type]
