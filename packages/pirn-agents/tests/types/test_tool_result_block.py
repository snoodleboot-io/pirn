"""Tests for ``ToolResultBlock.from_tool_result`` — the F1→F15 bridge (F15-S3 / PIR-361).

Covers projecting an F1 :class:`ToolResult` into a multimodal
:class:`ToolResultBlock`: a plain value degrades to text, an errored result uses
its error text, a lone block or a sequence of blocks (and a
:class:`MessageContent`) are carried through as nested blocks, and the answering
``call_id`` is preserved. Mirrored unittest+pytest style; stub doubles only.
"""

from __future__ import annotations

import unittest

from pirn_agents.types.image_block import ImageBlock
from pirn_agents.types.media_handle import MediaHandle
from pirn_agents.types.message_content import MessageContent
from pirn_agents.types.text_block import TextBlock
from pirn_agents.types.tool_result import ToolResult
from pirn_agents.types.tool_result_block import ToolResultBlock


def _image() -> ImageBlock:
    return ImageBlock(source=MediaHandle(media_type="image/png", data=b"d"), alt_text="chart")


class TestFromToolResult(unittest.TestCase):
    def test_string_result_degrades_to_text_block(self) -> None:
        block = ToolResultBlock.from_tool_result(ToolResult(call_id="c1", result="42 rows"))
        assert block.call_id == "c1"
        assert block.blocks == (TextBlock(text="42 rows"),)

    def test_non_string_scalar_uses_str(self) -> None:
        block = ToolResultBlock.from_tool_result(ToolResult(call_id="c1", result=42))
        assert block.blocks == (TextBlock(text="42"),)

    def test_none_result_yields_empty_text(self) -> None:
        block = ToolResultBlock.from_tool_result(ToolResult(call_id="c1", result=None))
        assert block.blocks == (TextBlock(text=""),)

    def test_error_result_uses_error_text(self) -> None:
        block = ToolResultBlock.from_tool_result(
            ToolResult(call_id="c1", result=None, error="boom")
        )
        assert block.blocks == (TextBlock(text="boom"),)

    def test_single_content_block_carried_through(self) -> None:
        img = _image()
        block = ToolResultBlock.from_tool_result(ToolResult(call_id="c1", result=img))
        assert block.blocks == (img,)
        assert block.as_text == "chart"

    def test_sequence_of_blocks_carried_through(self) -> None:
        img = _image()
        result = [TextBlock(text="see: "), img]
        block = ToolResultBlock.from_tool_result(ToolResult(call_id="c1", result=result))
        assert block.blocks == (TextBlock(text="see: "), img)

    def test_message_content_contributes_its_blocks(self) -> None:
        content = MessageContent.coerce([TextBlock(text="a"), _image()])
        block = ToolResultBlock.from_tool_result(ToolResult(call_id="c1", result=content))
        assert block.blocks == content.blocks

    def test_mixed_sequence_falls_back_to_text(self) -> None:
        block = ToolResultBlock.from_tool_result(
            ToolResult(call_id="c1", result=[TextBlock(text="a"), "raw"])
        )
        assert len(block.blocks) == 1
        assert isinstance(block.blocks[0], TextBlock)

    def test_rejects_non_tool_result(self) -> None:
        with self.assertRaises(TypeError):
            ToolResultBlock.from_tool_result("not-a-result")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
