"""Tests for the F15-S1 typed content-block model (PIR-353).

Covers construction and ``isinstance`` validation of every block variant, the
:class:`MediaHandle` by-reference / inline invariants (raw bytes never enter the
audit form), :class:`MessageContent` normalization/coercion, and the
backward-compatible :class:`AgentMessage` block projections.

Written in the mirrored unittest+pytest style: plain ``assert`` statements under
:class:`unittest.TestCase`, runnable by both ``pytest`` and ``python -m unittest``.
Stub doubles only — no backend imports.
"""

from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError

from pirn_agents.types.agent_message import AgentMessage
from pirn_agents.types.audio_block import AudioBlock
from pirn_agents.types.content_block import ContentBlock
from pirn_agents.types.file_block import FileBlock
from pirn_agents.types.image_block import ImageBlock
from pirn_agents.types.media_handle import MediaHandle
from pirn_agents.types.message_content import MessageContent
from pirn_agents.types.text_block import TextBlock
from pirn_agents.types.tool_result_block import ToolResultBlock


class TestMediaHandle(unittest.TestCase):
    def test_inline_payload_reports_inline(self) -> None:
        handle = MediaHandle(media_type="image/png", data=b"\x89PNG")
        assert handle.is_inline is True
        assert handle.uri is None

    def test_reference_payload_is_not_inline(self) -> None:
        handle = MediaHandle(media_type="image/png", uri="https://host/x.png")
        assert handle.is_inline is False
        assert handle.data is None

    def test_requires_exactly_one_source(self) -> None:
        with self.assertRaises(ValueError):
            MediaHandle(media_type="image/png")
        with self.assertRaises(ValueError):
            MediaHandle(media_type="image/png", uri="u", data=b"d")

    def test_rejects_empty_media_type(self) -> None:
        with self.assertRaises(TypeError):
            MediaHandle(media_type="", data=b"d")

    def test_audit_keeps_bytes_out_of_lineage(self) -> None:
        handle = MediaHandle(media_type="image/png", data=b"SECRETPIXELS")
        audit = handle._pirn_audit_dict()
        assert "SECRETPIXELS" not in str(audit)
        assert audit["size"] == len(b"SECRETPIXELS")
        assert audit["media_type"] == "image/png"

    def test_reference_audit_is_stable_descriptor(self) -> None:
        a = MediaHandle(media_type="image/png", uri="https://host/x.png")
        b = MediaHandle(media_type="image/png", uri="https://host/x.png")
        assert a._pirn_audit_dict() == b._pirn_audit_dict()
        assert a == b

    def test_frozen(self) -> None:
        handle = MediaHandle(media_type="image/png", data=b"d")
        with self.assertRaises(FrozenInstanceError):
            handle.media_type = "image/jpeg"  # type: ignore[misc]


class TestBlocks(unittest.TestCase):
    def test_text_block_projection_and_modality(self) -> None:
        block = TextBlock(text="hi")
        assert block.modality == "text"
        assert block.as_text == "hi"
        assert isinstance(block, ContentBlock)

    def test_text_block_rejects_non_str(self) -> None:
        with self.assertRaises(TypeError):
            TextBlock(text=123)  # type: ignore[arg-type]

    def test_image_block_alt_text_projection(self) -> None:
        block = ImageBlock(source=MediaHandle(media_type="image/png", data=b"d"), alt_text="cap")
        assert block.modality == "image"
        assert block.as_text == "cap"
        assert block._pirn_audit_dict()["modality"] == "image"

    def test_image_block_without_alt_projects_empty(self) -> None:
        block = ImageBlock(source=MediaHandle(media_type="image/png", data=b"d"))
        assert block.as_text == ""

    def test_image_block_rejects_non_handle_source(self) -> None:
        with self.assertRaises(TypeError):
            ImageBlock(source="not-a-handle")  # type: ignore[arg-type]

    def test_audio_block_transcript_projection(self) -> None:
        block = AudioBlock(source=MediaHandle(media_type="audio/wav", uri="u"), transcript="hello")
        assert block.modality == "audio"
        assert block.as_text == "hello"

    def test_file_block_filename_projection(self) -> None:
        block = FileBlock(
            source=MediaHandle(media_type="application/pdf", uri="u"), filename="r.pdf"
        )
        assert block.modality == "file"
        assert block.as_text == "r.pdf"

    def test_tool_result_block_nested_projection(self) -> None:
        img = ImageBlock(source=MediaHandle(media_type="image/png", data=b"d"), alt_text="chart")
        block = ToolResultBlock(call_id="c1", blocks=(TextBlock(text="see: "), img))
        assert block.modality == "tool_result"
        assert block.as_text == "see: chart"
        assert block._pirn_audit_dict()["call_id"] == "c1"

    def test_tool_result_block_rejects_non_block(self) -> None:
        with self.assertRaises(TypeError):
            ToolResultBlock(call_id="c1", blocks=("nope",))  # type: ignore[arg-type]


class TestMessageContent(unittest.TestCase):
    def test_coerce_str_to_single_text_block(self) -> None:
        content = MessageContent.coerce("plain")
        assert len(content) == 1
        assert isinstance(content.blocks[0], TextBlock)
        assert content.text == "plain"

    def test_coerce_single_block(self) -> None:
        block = TextBlock(text="x")
        assert MessageContent.coerce(block).blocks == (block,)

    def test_coerce_sequence(self) -> None:
        img = ImageBlock(source=MediaHandle(media_type="image/png", data=b"d"), alt_text="a")
        content = MessageContent.coerce([TextBlock(text="t"), img])
        assert len(content) == 2
        assert content.text == "ta"

    def test_coerce_idempotent_on_message_content(self) -> None:
        content = MessageContent.coerce("x")
        assert MessageContent.coerce(content) is content

    def test_coerce_rejects_bad_type(self) -> None:
        with self.assertRaises(TypeError):
            MessageContent.coerce(42)  # type: ignore[arg-type]

    def test_rejects_non_block_item(self) -> None:
        with self.assertRaises(TypeError):
            MessageContent(blocks=("nope",))  # type: ignore[arg-type]

    def test_iteration_and_audit(self) -> None:
        content = MessageContent.coerce([TextBlock(text="a"), TextBlock(text="b")])
        assert [b.as_text for b in content] == ["a", "b"]
        assert content._pirn_audit_dict()["blocks"][0]["text"] == "a"


class TestAgentMessageBackwardCompat(unittest.TestCase):
    def test_plain_string_still_works(self) -> None:
        msg = AgentMessage(role="user", content="hello")
        assert msg.content == "hello"
        assert msg.text == "hello"
        assert msg.blocks is None

    def test_plain_string_coerces_to_single_text_block(self) -> None:
        msg = AgentMessage(role="user", content="hello")
        blocks = msg.content_blocks
        assert len(blocks) == 1
        assert isinstance(blocks[0], TextBlock)
        assert blocks[0].as_text == "hello"

    def test_from_blocks_projects_text_into_content(self) -> None:
        img = ImageBlock(source=MediaHandle(media_type="image/png", data=b"d"), alt_text="chart")
        msg = AgentMessage.from_blocks(role="user", blocks=[TextBlock(text="look: "), img])
        assert msg.content == "look: chart"
        assert msg.text == "look: chart"
        assert msg.blocks is not None
        assert msg.content_blocks == (TextBlock(text="look: "), img)

    def test_blocks_validated_via_isinstance(self) -> None:
        with self.assertRaises(TypeError):
            AgentMessage(role="user", content="", blocks=("nope",))  # type: ignore[arg-type]

    def test_from_blocks_rejects_non_block(self) -> None:
        with self.assertRaises(TypeError):
            AgentMessage.from_blocks(role="user", blocks=["nope"])  # type: ignore[list-item]

    def test_audit_includes_blocks_and_hides_bytes(self) -> None:
        img = ImageBlock(source=MediaHandle(media_type="image/png", data=b"RAWPIXELS"))
        msg = AgentMessage.from_blocks(role="user", blocks=[img])
        audit = msg._pirn_audit_dict()
        assert audit["blocks"] is not None
        assert "RAWPIXELS" not in str(audit)

    def test_text_only_audit_blocks_none(self) -> None:
        msg = AgentMessage(role="user", content="hi")
        assert msg._pirn_audit_dict()["blocks"] is None


if __name__ == "__main__":
    unittest.main()
