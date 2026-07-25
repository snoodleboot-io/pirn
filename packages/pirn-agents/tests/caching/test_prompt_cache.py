"""Mirrored tests for :class:`PromptCache` — exact, semantic, TTL, invalidation (PIR-492).

The embedder is a deterministic stub and the clock is hand-cranked, so every
hit path, TTL expiry, and eviction is fully reproducible with no backend.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence

import pytest

from pirn_agents.caching.prompt_cache import PromptCache


class _StubEmbedder:
    """Maps known prompts to fixed vectors; unknown prompts to a distant vector."""

    def __init__(self, table: dict[str, Sequence[float]]) -> None:
        self._table = table
        self.calls = 0

    async def __call__(self, text: str) -> Sequence[float]:
        self.calls += 1
        return self._table.get(text, (0.0, 0.0, 1.0))


class _FakeClock:
    """A hand-cranked monotonic clock for deterministic TTL tests."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def _counter() -> tuple[list[int], Callable[[], Awaitable[int]]]:
    """Return (calls, compute) where compute increments and returns the count."""
    calls: list[int] = [0]

    async def compute() -> int:
        calls[0] += 1
        return calls[0]

    return calls, compute


class TestValidation:
    def test_bad_threshold_rejected(self) -> None:
        with pytest.raises(ValueError, match="threshold"):
            PromptCache(threshold=1.5)

    def test_negative_ttl_rejected(self) -> None:
        with pytest.raises(ValueError, match="ttl_seconds"):
            PromptCache(ttl_seconds=-1.0)

    def test_bad_max_entries_rejected(self) -> None:
        with pytest.raises(ValueError, match="max_entries"):
            PromptCache(max_entries=0)


class TestExactCache:
    async def test_identical_prompt_short_circuits(self) -> None:
        cache = PromptCache()
        calls, compute = _counter()

        first = await cache.get_or_compute("hello", compute)
        second = await cache.get_or_compute("hello", compute)

        assert first == second == 1
        assert calls[0] == 1  # second served from exact cache
        assert cache.hits == 1

    async def test_params_partition_the_key(self) -> None:
        cache = PromptCache()
        calls, compute = _counter()

        await cache.get_or_compute("hi", compute, params={"model": "cheap"})
        await cache.get_or_compute("hi", compute, params={"model": "strong"})

        assert calls[0] == 2  # differing params never collide


class TestSemanticCache:
    async def test_near_duplicate_prompt_hits(self) -> None:
        embed = _StubEmbedder(
            {
                "capital of france": (1.0, 0.0, 0.0),
                "france's capital": (0.99, 0.01, 0.0),
            }
        )
        cache = PromptCache(embed=embed, threshold=0.95)
        calls, compute = _counter()

        await cache.get_or_compute("capital of france", compute)
        result = await cache.get_or_compute("france's capital", compute)

        assert result == 1
        assert calls[0] == 1  # second served semantically
        assert cache.semantic_hits == 1

    async def test_dissimilar_prompt_misses(self) -> None:
        embed = _StubEmbedder({"weather": (1.0, 0.0, 0.0), "stocks": (0.0, 1.0, 0.0)})
        cache = PromptCache(embed=embed, threshold=0.95)
        calls, compute = _counter()

        await cache.get_or_compute("weather", compute)
        await cache.get_or_compute("stocks", compute)

        assert calls[0] == 2  # orthogonal -> no false hit


class TestTtlAndInvalidation:
    async def test_expired_exact_entry_is_evicted_and_recomputed(self) -> None:
        clock = _FakeClock()
        cache = PromptCache(ttl_seconds=10.0, clock=clock)
        calls, compute = _counter()

        await cache.get_or_compute("q", compute)
        clock.now = 5.0
        await cache.get_or_compute("q", compute)  # still fresh: hit
        assert calls[0] == 1
        clock.now = 10.0  # at expiry -> expired
        await cache.get_or_compute("q", compute)
        assert calls[0] == 2  # recomputed after expiry

    async def test_expired_entry_does_not_semantically_hit(self) -> None:
        clock = _FakeClock()
        embed = _StubEmbedder({"a": (1.0, 0.0, 0.0), "a-ish": (0.999, 0.001, 0.0)})
        cache = PromptCache(embed=embed, threshold=0.95, ttl_seconds=10.0, clock=clock)
        calls, compute = _counter()

        await cache.get_or_compute("a", compute)
        clock.now = 20.0  # first entry now expired
        await cache.get_or_compute("a-ish", compute)
        assert calls[0] == 2  # expired neighbour not reused

    async def test_explicit_invalidate_forces_recompute(self) -> None:
        cache = PromptCache()
        calls, compute = _counter()

        await cache.get_or_compute("p", compute)
        cache.invalidate("p")
        await cache.get_or_compute("p", compute)

        assert calls[0] == 2

    async def test_purge_expired_reports_count(self) -> None:
        clock = _FakeClock()
        cache = PromptCache(ttl_seconds=1.0, clock=clock)
        _, compute = _counter()

        await cache.get_or_compute("x", compute)
        await cache.get_or_compute("y", compute)
        assert len(cache) == 2
        clock.now = 5.0
        assert cache.purge_expired() == 2
        assert len(cache) == 0


class TestEviction:
    async def test_fifo_bound_enforced(self) -> None:
        cache = PromptCache(max_entries=1)
        _, compute = _counter()

        await cache.get_or_compute("one", compute)
        await cache.get_or_compute("two", compute)

        assert len(cache) == 1  # oldest evicted at the bound
