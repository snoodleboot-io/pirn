"""Tests for the lexical chunking strategies (F25-S2): fixed, recursive, sentence.

Each strategy is exercised directly over in-memory text — happy path, empty
input, the shared non-string guard, and constructor validation.
"""

from __future__ import annotations

import unittest

from pirn_agents.specializations.document_processing.chunking.chunk import Chunk
from pirn_agents.specializations.document_processing.chunking.fixed_size_chunking_strategy import (
    FixedSizeChunkingStrategy,
)
from pirn_agents.specializations.document_processing.chunking.recursive_character_chunking_strategy import (
    RecursiveCharacterChunkingStrategy,
)
from pirn_agents.specializations.document_processing.chunking.sentence_window_chunking_strategy import (
    SentenceWindowChunkingStrategy,
)


class TestFixedSizeChunkingStrategy(unittest.IsolatedAsyncioTestCase):
    async def test_windows_cover_full_text(self) -> None:
        chunks = await FixedSizeChunkingStrategy(chunk_size=10, chunk_overlap=0).chunk(
            "abcdefghijklmno"
        )
        assert [c.text for c in chunks] == ["abcdefghij", "klmno"]
        assert all(isinstance(c, Chunk) for c in chunks)
        assert [c.index for c in chunks] == [0, 1]
        assert chunks[0].metadata == {"start_char": 0, "end_char": 10}

    async def test_overlap_shares_characters(self) -> None:
        chunks = await FixedSizeChunkingStrategy(chunk_size=6, chunk_overlap=2).chunk("abcdefghij")
        assert chunks[0].text == "abcdef"
        assert chunks[1].text.startswith("ef")

    async def test_empty_text_returns_empty(self) -> None:
        assert await FixedSizeChunkingStrategy().chunk("") == []

    async def test_non_string_raises(self) -> None:
        with self.assertRaisesRegex(TypeError, "must be a string"):
            await FixedSizeChunkingStrategy().chunk(b"bytes")  # type: ignore[arg-type]

    def test_invalid_overlap_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "chunk_overlap"):
            FixedSizeChunkingStrategy(chunk_size=5, chunk_overlap=5)

    def test_invalid_size_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "chunk_size"):
            FixedSizeChunkingStrategy(chunk_size=0)


class TestRecursiveCharacterChunkingStrategy(unittest.IsolatedAsyncioTestCase):
    async def test_respects_size_cap(self) -> None:
        text = "para one here.\n\npara two here.\n\npara three is longer than the rest of them."
        chunks = await RecursiveCharacterChunkingStrategy(chunk_size=30, chunk_overlap=5).chunk(
            text
        )
        assert chunks
        assert all(len(c.text) <= 30 for c in chunks)
        assert [c.index for c in chunks] == list(range(len(chunks)))

    async def test_prefers_paragraph_boundaries(self) -> None:
        text = "alpha\n\nbeta\n\ngamma"
        chunks = await RecursiveCharacterChunkingStrategy(chunk_size=5, chunk_overlap=0).chunk(text)
        assert {c.text for c in chunks} == {"alpha", "beta", "gamma"}

    async def test_empty_returns_empty(self) -> None:
        assert await RecursiveCharacterChunkingStrategy().chunk("") == []

    def test_empty_separators_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "separators"):
            RecursiveCharacterChunkingStrategy(separators=())


class TestSentenceWindowChunkingStrategy(unittest.IsolatedAsyncioTestCase):
    async def test_windows_of_sentences(self) -> None:
        text = "One. Two. Three. Four."
        chunks = await SentenceWindowChunkingStrategy(window_size=2, window_overlap=1).chunk(text)
        assert [c.text for c in chunks] == ["One. Two.", "Two. Three.", "Three. Four."]
        assert chunks[0].metadata == {"sentence_start": 0, "sentence_count": 2}

    async def test_no_overlap(self) -> None:
        text = "One. Two. Three. Four."
        chunks = await SentenceWindowChunkingStrategy(window_size=2, window_overlap=0).chunk(text)
        assert [c.text for c in chunks] == ["One. Two.", "Three. Four."]

    async def test_empty_returns_empty(self) -> None:
        assert await SentenceWindowChunkingStrategy().chunk("   ") == []

    def test_invalid_overlap_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "window_overlap"):
            SentenceWindowChunkingStrategy(window_size=2, window_overlap=2)


if __name__ == "__main__":
    unittest.main()
