"""Unit tests for :class:`FactClaimVerifier`."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from typing import Any
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.agents.memory_store import MemoryStore
from pirn.domains.agents.specializations.guardrails.fact_claim_verifier import (
    FactClaimVerifier,
)
from pirn.domains.agents.types.agent_response import AgentResponse
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


class TestFactClaimVerifierConstruction(unittest.TestCase):
    def test_rejects_non_memory_store(self) -> None:
        with self.assertRaisesRegex(TypeError, "MemoryStore"):
            with Tapestry():
                FactClaimVerifier(
                    response=AgentResponse(content="ok", finish_reason="stop"),
                    claims=["claim"],
                    store="bad",  # type: ignore[arg-type]
                    _config=KnotConfig(id="fcv"),
                )


class TestFactClaimVerifierProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_original_response_when_all_verified(self) -> None:
        store = _HitStore(supported=("water is wet",))
        response = AgentResponse(content="ok", finish_reason="stop")
        with Tapestry() as t:
            FactClaimVerifier(
                response=response,
                claims=["water is wet"],
                store=store,
                _config=KnotConfig(id="fcv"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["fcv"]
        assert out.content == "ok"

    async def test_appends_warning_for_unverified_claim(self) -> None:
        store = _HitStore(supported=())  # no hits
        response = AgentResponse(content="The moon is cheese.", finish_reason="stop")
        with Tapestry() as t:
            FactClaimVerifier(
                response=response,
                claims=["moon is cheese"],
                store=store,
                _config=KnotConfig(id="fcv"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["fcv"]
        assert "Unverified" in out.content
        assert "moon is cheese" in out.content

    async def test_rejects_non_agent_response(self) -> None:
        store = _HitStore(supported=())
        with Tapestry():
            with self.assertRaises(TypeError):
                FactClaimVerifier(
                    response="not-a-response",  # type: ignore[arg-type]
                    claims=[],
                    store=store,
                    _config=KnotConfig(id="fcv"),
                )
