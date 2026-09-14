"""Unit tests for :class:`FactClaimVerifier`.

PIR-867: each claim's search is independent of every other claim's, so
``FactClaimVerifier`` fans them out (one ``ClaimVerification`` knot per claim
wired into an ``Aggregator``) rather than awaiting ``store.search`` in a
hand-rolled ``for`` loop. ``process`` therefore returns the sink of an inner
pipeline instead of the annotated ``AgentResponse`` directly, so the outcome
tests run a real tapestry and read the verifier's output (the pattern
PIR-856 established for ``ParallelToolCaller``). Input-validation tests still
call ``__call__`` directly with a parent-results mapping, exactly as before.
"""

from __future__ import annotations

import unittest
from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.err import Err
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.memory.stores.memory_store import MemoryStore
from pirn_agents.specializations.guardrails.fact_claim_verifier import (
    FactClaimVerifier,
)
from pirn_agents.types.messaging.agent_response import AgentResponse


class _HitStore(MemoryStore):
    """Returns one hit for queries containing supported substrings."""

    def __init__(self, supported: tuple[str, ...]) -> None:
        self._supported = supported

    async def store(self, key, value) -> None:
        pass

    async def retrieve(self, key) -> None:
        return None

    async def search(self, query, *, top_k=10) -> Sequence[Mapping[str, Any]]:
        has_hit = any(s in query for s in self._supported)
        return [{"fact": query}] if has_hit else []

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
        with Tapestry() as t:
            FactClaimVerifier(
                response=response,
                claims=["water is wet"],
                store=store,
                _config=KnotConfig(id="fcv"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded, result.exceptions
        assert result.outputs["fcv"].content == "ok"

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
        assert result.succeeded, result.exceptions
        out = result.outputs["fcv"]
        assert "Unverified" in out.content
        assert "moon is cheese" in out.content

    async def test_no_valid_claims_returns_original_response(self) -> None:
        store = _HitStore(supported=())
        response = AgentResponse(content="ok", finish_reason="stop")
        with Tapestry() as t:
            FactClaimVerifier(
                response=response,
                claims=[""],
                store=store,
                _config=KnotConfig(id="fcv"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded, result.exceptions
        assert result.outputs["fcv"].content == "ok"

    async def test_mixed_claims_only_unverified_ones_listed(self) -> None:
        store = _HitStore(supported=("water is wet",))
        response = AgentResponse(content="ok", finish_reason="stop")
        with Tapestry() as t:
            FactClaimVerifier(
                response=response,
                claims=["water is wet", "moon is cheese"],
                store=store,
                _config=KnotConfig(id="fcv"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded, result.exceptions
        out = result.outputs["fcv"]
        assert "moon is cheese" in out.content
        assert "water is wet" not in out.content.split("Unverified claims:")[1]

    async def test_rejects_non_agent_response(self) -> None:
        store = _HitStore(supported=())
        k = _make_knot(store)
        result = await k({"response": "not-a-response", "claims": [], "store": store})
        assert isinstance(result, Err)
        assert result.record.exc_type == "ValidationError"

    async def test_each_claim_gets_its_own_lineage_row(self) -> None:
        """PIR-867: each claim is a node now, not an inline await in a for loop."""
        store = _HitStore(supported=("water is wet",))
        response = AgentResponse(content="ok", finish_reason="stop")
        with Tapestry() as t:
            FactClaimVerifier(
                response=response,
                claims=["water is wet", "moon is cheese"],
                store=store,
                _config=KnotConfig(id="fcv"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded, result.exceptions
        children = await t.history.children_of(result.run_id)
        inner_knot_ids = {row.knot_id for child in children for row in child.lineage}
        assert {"verify_0", "verify_1"} <= inner_knot_ids, inner_knot_ids


if __name__ == "__main__":
    unittest.main()
