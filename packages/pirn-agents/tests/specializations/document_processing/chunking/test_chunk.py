"""Unit tests for :class:`Chunk` invariants."""

from __future__ import annotations

import unittest

from pirn_agents.specializations.document_processing.chunking.chunk import Chunk


class TestChunk(unittest.TestCase):
    def test_valid_chunk_is_constructed(self) -> None:
        chunk = Chunk(text="hello", index=0, metadata={"length": 5})
        assert (chunk.text, chunk.index, chunk.metadata) == ("hello", 0, {"length": 5})

    def test_metadata_defaults_to_empty(self) -> None:
        chunk = Chunk(text="body", index=3)
        assert chunk.metadata == {}

    def test_rejects_empty_text(self) -> None:
        with self.assertRaises(ValueError):
            Chunk(text="", index=0)

    def test_rejects_non_str_text(self) -> None:
        with self.assertRaises(TypeError):
            Chunk(text=123, index=0)  # type: ignore[arg-type]

    def test_rejects_negative_index(self) -> None:
        with self.assertRaises(ValueError):
            Chunk(text="body", index=-1)

    def test_rejects_bool_index(self) -> None:
        with self.assertRaises(TypeError):
            Chunk(text="body", index=True)  # type: ignore[arg-type]

    def test_rejects_non_mapping_metadata(self) -> None:
        with self.assertRaises(TypeError):
            Chunk(text="body", index=0, metadata=["not", "a", "map"])  # type: ignore[arg-type]
