"""Benchmark: ContentHasher.hash overhead for various payload sizes.

Run with:
    pytest tests/perf/bench_hashing.py --benchmark-only
"""

from __future__ import annotations

import pytest

from pirn.core.content_hasher import ContentHasher


@pytest.mark.benchmark(group="hashing")
def test_bench_hash_small_dict(benchmark):
    data = {"key": "value", "number": 42, "nested": {"a": 1, "b": 2}}
    benchmark(ContentHasher.hash, data)


@pytest.mark.benchmark(group="hashing")
def test_bench_hash_1mb_bytes(benchmark):
    data = b"x" * (1024 * 1024)
    benchmark(ContentHasher.hash, data)


@pytest.mark.benchmark(group="hashing")
def test_bench_hash_10mb_bytes(benchmark):
    data = b"x" * (10 * 1024 * 1024)
    benchmark(ContentHasher.hash, data)


@pytest.mark.benchmark(group="hashing")
def test_bench_hash_100mb_bytes(benchmark):
    data = b"x" * (100 * 1024 * 1024)
    benchmark(ContentHasher.hash, data)


@pytest.mark.benchmark(group="hashing")
def test_bench_hash_large_list(benchmark):
    data = list(range(10_000))
    benchmark(ContentHasher.hash, data)
