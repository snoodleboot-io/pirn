"""Tests for :class:`ClaimVerification` (PIR-874: returns evidence, not a bool)."""

from __future__ import annotations

import unittest
from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.memory.stores.memory_store import MemoryStore
from pirn_agents.specializations.guardrails.claim_support import ClaimSupport
from pirn_agents.specializations.guardrails.claim_verification import ClaimVerification


class _Store(MemoryStore):
    def __init__(self, hits: Sequence[Mapping[str, Any]]) -> None:
        self._hits = hits

    async def store(self, key, value) -> None:
        pass

    async def retrieve(self, key) -> None:
        return None

    async def search(self, query, *, top_k=10) -> Sequence[Mapping[str, Any]]:
        return self._hits

    async def forget(self, key) -> None:
        pass

    async def close(self) -> None:
        pass


class TestClaimVerification(unittest.IsolatedAsyncioTestCase):
    async def _run(self, hits: Sequence[Mapping[str, Any]]) -> ClaimSupport:
        with Tapestry() as t:
            ClaimVerification(claim="c", store=_Store(hits), _config=KnotConfig(id="cv"))
        result = await t.run(RunRequest())
        assert result.succeeded, result.exceptions
        return result.outputs["cv"]

    async def test_returns_hits_as_evidence(self) -> None:
        out = await self._run([{"fact": "c"}])
        assert isinstance(out, ClaimSupport)
        assert out.data == ({"fact": "c"},)
        assert out.metadata.supported is True

    async def test_no_hits_is_unsupported(self) -> None:
        out = await self._run([])
        assert out.metadata.supported is False
        assert out.data == ()


if __name__ == "__main__":
    unittest.main()
