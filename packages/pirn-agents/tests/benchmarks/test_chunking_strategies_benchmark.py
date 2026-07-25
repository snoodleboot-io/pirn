"""Chunking-strategy comparison benchmark (F25-S2-T3 / PIR-607).

Runs every lexical chunking strategy over one fixed sample corpus and records
chunk-count and latency per strategy, so a reviewer can compare chunk
granularity and cost across strategies at a glance. Uses only in-memory text and
no embedding backend (the semantic strategy is covered by its unit tests with a
stub embedder).
"""

from __future__ import annotations

import time

import pytest

from pirn_agents.specializations.document_processing.chunking.chunking_strategy import (
    ChunkingStrategy,
)
from pirn_agents.specializations.document_processing.chunking.code_aware_chunking_strategy import (
    CodeAwareChunkingStrategy,
)
from pirn_agents.specializations.document_processing.chunking.fixed_size_chunking_strategy import (
    FixedSizeChunkingStrategy,
)
from pirn_agents.specializations.document_processing.chunking.parent_child_chunking_strategy import (
    ParentChildChunkingStrategy,
)
from pirn_agents.specializations.document_processing.chunking.recursive_character_chunking_strategy import (
    RecursiveCharacterChunkingStrategy,
)
from pirn_agents.specializations.document_processing.chunking.sentence_window_chunking_strategy import (
    SentenceWindowChunkingStrategy,
)
from tests.benchmarks.conftest import BenchmarkRecorder

_CORPUS = (
    "The quick brown fox jumps over the lazy dog. "
    "Retrieval augmented generation grounds a model in a corpus. "
    "Chunking decides what a retriever can recall.\n\n"
) * 40


async def _measure(strategy: ChunkingStrategy, text: str) -> tuple[int, float]:
    start = time.perf_counter()
    chunks = await strategy.chunk(text)
    return len(chunks), time.perf_counter() - start


@pytest.mark.benchmark
async def test_chunking_strategies_comparison(
    benchmark_recorder: BenchmarkRecorder,
) -> None:
    strategies: dict[str, ChunkingStrategy] = {
        "fixed": FixedSizeChunkingStrategy(chunk_size=200, chunk_overlap=20),
        "recursive": RecursiveCharacterChunkingStrategy(chunk_size=200, chunk_overlap=20),
        "sentence": SentenceWindowChunkingStrategy(window_size=3, window_overlap=1),
        "parent_child": ParentChildChunkingStrategy(child_size=120, child_overlap=10),
        "code_aware": CodeAwareChunkingStrategy(max_chars=200),
    }
    for name, strategy in strategies.items():
        count, elapsed = await _measure(strategy, _CORPUS)
        assert count > 0
        assert elapsed < 1.0
        benchmark_recorder.record(f"Chunking_{name}", chunk_count=float(count), seconds=elapsed)


if __name__ == "__main__":
    import unittest

    unittest.main()
