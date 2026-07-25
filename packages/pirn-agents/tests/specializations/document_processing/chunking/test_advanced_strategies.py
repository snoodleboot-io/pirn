"""Tests for the advanced chunking strategies (F25-S2): semantic, parent-child, code-aware.

The semantic strategy is driven by a scripted stub embedder so breakpoints are
deterministic and no real embedding backend is touched.
"""

from __future__ import annotations

import unittest

from pirn_agents.specializations.document_processing.chunking.code_aware_chunking_strategy import (
    CodeAwareChunkingStrategy,
)
from pirn_agents.specializations.document_processing.chunking.parent_child_chunking_strategy import (
    ParentChildChunkingStrategy,
)
from pirn_agents.specializations.document_processing.chunking.semantic_chunking_strategy import (
    SemanticChunkingStrategy,
)
from tests.specializations.conftest import StubEmbeddingProvider


class TestSemanticChunkingStrategy(unittest.IsolatedAsyncioTestCase):
    async def test_breaks_where_similarity_drops(self) -> None:
        # Sentences 0,1 share a vector; sentence 2 is orthogonal -> break before it.
        embedder = StubEmbeddingProvider(vectors=[[1.0, 0.0], [1.0, 0.0], [0.0, 1.0]])
        strategy = SemanticChunkingStrategy(embedder=embedder, breakpoint_distance=0.5)
        chunks = await strategy.chunk("First one. Second one. Third one.")
        assert [c.text for c in chunks] == ["First one. Second one.", "Third one."]
        assert chunks[0].metadata == {"sentence_start": 0, "sentence_count": 2}

    async def test_max_sentences_forces_break(self) -> None:
        embedder = StubEmbeddingProvider(vectors=[[1.0, 0.0]])  # all identical -> never a boundary
        strategy = SemanticChunkingStrategy(
            embedder=embedder, breakpoint_distance=1.9, max_sentences=1
        )
        chunks = await strategy.chunk("A a. B b. C c.")
        assert len(chunks) == 3

    async def test_single_sentence_single_chunk(self) -> None:
        strategy = SemanticChunkingStrategy(embedder=StubEmbeddingProvider())
        chunks = await strategy.chunk("Only one sentence here")
        assert len(chunks) == 1
        assert chunks[0].metadata["sentence_count"] == 1

    async def test_empty_returns_empty(self) -> None:
        strategy = SemanticChunkingStrategy(embedder=StubEmbeddingProvider())
        assert await strategy.chunk("") == []

    def test_rejects_non_embedding_provider(self) -> None:
        with self.assertRaisesRegex(TypeError, "EmbeddingProvider"):
            SemanticChunkingStrategy(embedder=object())  # type: ignore[arg-type]

    def test_rejects_out_of_range_distance(self) -> None:
        with self.assertRaisesRegex(ValueError, "breakpoint_distance"):
            SemanticChunkingStrategy(embedder=StubEmbeddingProvider(), breakpoint_distance=3.0)


class TestParentChildChunkingStrategy(unittest.IsolatedAsyncioTestCase):
    async def test_children_carry_parent_context(self) -> None:
        strategy = ParentChildChunkingStrategy(child_size=5, child_overlap=0, group_size=2)
        chunks = await strategy.chunk("abcdefghij")
        assert [c.text for c in chunks] == ["abcde", "fghij"]
        assert chunks[0].metadata["kind"] == "child"
        assert chunks[0].metadata["parent_index"] == 0
        assert chunks[1].metadata["parent_index"] == 0
        assert "abcde" in chunks[0].metadata["parent_text"]

    async def test_second_parent_group(self) -> None:
        strategy = ParentChildChunkingStrategy(child_size=2, child_overlap=0, group_size=2)
        chunks = await strategy.chunk("aabbccdd")
        assert [c.metadata["parent_index"] for c in chunks] == [0, 0, 1, 1]

    async def test_empty_returns_empty(self) -> None:
        assert await ParentChildChunkingStrategy().chunk("") == []

    def test_invalid_group_size_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "group_size"):
            ParentChildChunkingStrategy(group_size=0)


class TestCodeAwareChunkingStrategy(unittest.IsolatedAsyncioTestCase):
    async def test_splits_on_definitions(self) -> None:
        code = "def a():\n    return 1\n\ndef b():\n    return 2\n"
        chunks = await CodeAwareChunkingStrategy(max_chars=20).chunk(code)
        firsts = [c.text.splitlines()[0] for c in chunks]
        assert "def a():" in firsts
        assert "def b():" in firsts

    async def test_merges_small_blocks_under_cap(self) -> None:
        code = "def a():\n    pass\n\ndef b():\n    pass\n"
        chunks = await CodeAwareChunkingStrategy(max_chars=1000).chunk(code)
        assert len(chunks) == 1

    async def test_blank_only_returns_empty(self) -> None:
        assert await CodeAwareChunkingStrategy().chunk("   \n\n  ") == []

    def test_invalid_max_chars_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "max_chars"):
            CodeAwareChunkingStrategy(max_chars=0)


if __name__ == "__main__":
    unittest.main()
