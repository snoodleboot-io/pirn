"""Mirrored tests for :class:`SemanticResultCache` similarity matching (PIR-292).

The embedding function is a deterministic stub (no vendor backend), so the
similarity threshold behaviour is fully reproducible.
"""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from pirn_agents.caching.cache_entry import CacheEntry
from pirn_agents.caching.semantic_result_cache import SemanticResultCache


class _StubEmbedder:
    """Maps known phrases to fixed vectors; unknown phrases to a distant vector."""

    def __init__(self, table: dict[str, Sequence[float]]) -> None:
        self._table = table
        self.calls = 0

    async def __call__(self, text: str) -> Sequence[float]:
        self.calls += 1
        return self._table.get(text, (0.0, 0.0, 1.0))


class TestValidation:
    def test_bad_threshold_rejected(self) -> None:
        with pytest.raises(ValueError, match="threshold"):
            SemanticResultCache(embed=_StubEmbedder({}), threshold=1.5)

    def test_bad_max_entries_rejected(self) -> None:
        with pytest.raises(ValueError, match="max_entries"):
            SemanticResultCache(embed=_StubEmbedder({}), max_entries=0)


class TestSemanticMatching:
    async def test_near_identical_query_hits(self) -> None:
        embed = _StubEmbedder(
            {
                "capital of france": (1.0, 0.0, 0.0),
                "france's capital": (0.99, 0.01, 0.0),  # cosine ~1.0
            }
        )
        cache = SemanticResultCache(embed=embed, threshold=0.95)
        compute_calls = 0

        async def compute() -> str:
            nonlocal compute_calls
            compute_calls += 1
            return "Paris"

        first = await cache.get_or_compute_semantic("capital of france", compute)
        second = await cache.get_or_compute_semantic("france's capital", compute)
        assert first == second == "Paris"
        assert compute_calls == 1  # second served by semantic similarity
        assert cache.hits == 1

    async def test_dissimilar_query_misses(self) -> None:
        embed = _StubEmbedder(
            {
                "weather today": (1.0, 0.0, 0.0),
                "stock prices": (0.0, 1.0, 0.0),  # orthogonal -> cosine 0
            }
        )
        cache = SemanticResultCache(embed=embed, threshold=0.95)
        compute_calls = 0

        async def compute() -> int:
            nonlocal compute_calls
            compute_calls += 1
            return compute_calls

        await cache.get_or_compute_semantic("weather today", compute)
        await cache.get_or_compute_semantic("stock prices", compute)
        assert compute_calls == 2  # no false hit

    async def test_exact_key_interface_still_works(self) -> None:
        cache = SemanticResultCache(embed=_StubEmbedder({}))
        await cache.put(CacheEntry(key="k", value="v"))
        entry = await cache.get("k")
        assert entry is not None and entry.value == "v"
        await cache.invalidate("k")
        assert await cache.get("k") is None
