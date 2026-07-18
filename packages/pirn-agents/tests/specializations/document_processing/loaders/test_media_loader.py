"""Tests for ``MediaLoader`` + ``LoadedDocument.blocks`` — the F25 seam (F15-S4 / PIR-365).

Covers the multimodal loader framing raw bytes into a :class:`LoadedDocument`
whose typed :attr:`blocks` carries an image/audio/file block chosen from the
media type, with a text projection for graceful degradation, and the
backward-compatible ``blocks=None`` default plus its ``isinstance`` validation.
Mirrored unittest+pytest style; in-memory bytes only, no backend.
"""

from __future__ import annotations

import unittest

from pirn_agents.specializations.document_processing.loaders.loaded_document import (
    LoadedDocument,
)
from pirn_agents.specializations.document_processing.loaders.media_loader import MediaLoader
from pirn_agents.types.audio_block import AudioBlock
from pirn_agents.types.file_block import FileBlock
from pirn_agents.types.image_block import ImageBlock
from pirn_agents.types.text_block import TextBlock


class TestMediaLoader(unittest.IsolatedAsyncioTestCase):
    async def test_image_media_type_emits_image_block(self) -> None:
        doc = await MediaLoader(media_type="image/png", caption="chart").load(b"\x89PNG")
        assert doc.blocks is not None
        assert isinstance(doc.blocks[0], ImageBlock)
        assert doc.blocks[0].source.data == b"\x89PNG"
        assert doc.text == "chart"
        assert doc.metadata["content_type"] == "image/png"

    async def test_audio_media_type_emits_audio_block(self) -> None:
        doc = await MediaLoader(media_type="audio/wav").load(b"RIFF")
        assert isinstance(doc.blocks[0], AudioBlock)

    async def test_other_media_type_emits_file_block(self) -> None:
        doc = await MediaLoader(media_type="application/pdf", caption="r.pdf").load(b"%PDF")
        assert isinstance(doc.blocks[0], FileBlock)
        assert doc.blocks[0].filename == "r.pdf"

    async def test_source_id_recorded(self) -> None:
        doc = await MediaLoader(media_type="image/png").load(b"d", source_id="s3://b/k")
        assert doc.source_id == "s3://b/k"

    async def test_rejects_non_bytes(self) -> None:
        with self.assertRaises(TypeError):
            await MediaLoader(media_type="image/png").load("not-bytes")  # type: ignore[arg-type]

    def test_rejects_empty_media_type(self) -> None:
        with self.assertRaises(TypeError):
            MediaLoader(media_type="")

    def test_rejects_bad_caption(self) -> None:
        with self.assertRaises(TypeError):
            MediaLoader(media_type="image/png", caption=123)  # type: ignore[arg-type]


class TestLoadedDocumentBlocks(unittest.TestCase):
    def test_text_only_default_blocks_none(self) -> None:
        doc = LoadedDocument(text="hello")
        assert doc.blocks is None

    def test_blocks_accepts_content_blocks(self) -> None:
        doc = LoadedDocument(text="", blocks=(TextBlock(text="x"),))
        assert doc.blocks == (TextBlock(text="x"),)

    def test_rejects_non_block_in_blocks(self) -> None:
        with self.assertRaises(TypeError):
            LoadedDocument(text="", blocks=("nope",))  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
