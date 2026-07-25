"""Tests for the F15-S2 multimodal encode/decode adapters (PIR-357).

Covers the provider-neutral :class:`MultimodalAdapter` base (capability gating,
graceful degradation, fail-loud default, decode) via a stub adapter, plus both
concrete peers — :class:`OpenAICompatibleMultimodalAdapter` and
:class:`AnthropicMessagesMultimodalAdapter` — round-tripping inline and
referenced media. The two wire formats differ (URL string vs typed ``source``
object; Anthropic carries no audio) to prove no vendor is privileged. Mirrored
unittest+pytest style; stub doubles only, no backend imports.
"""

from __future__ import annotations

import unittest
from typing import Any

from pirn_agents.exceptions.unsupported_modality_error import UnsupportedModalityError
from pirn_agents.llm.anthropic_messages_multimodal_adapter import (
    AnthropicMessagesMultimodalAdapter,
)
from pirn_agents.llm.modality_capability import ModalityCapability
from pirn_agents.llm.multimodal_adapter import MultimodalAdapter
from pirn_agents.llm.openai_compatible_multimodal_adapter import (
    OpenAICompatibleMultimodalAdapter,
)
from pirn_agents.types.audio_block import AudioBlock
from pirn_agents.types.content_block import ContentBlock
from pirn_agents.types.file_block import FileBlock
from pirn_agents.types.image_block import ImageBlock
from pirn_agents.types.media_handle import MediaHandle
from pirn_agents.types.text_block import TextBlock


class _ImageOnlyAdapter(MultimodalAdapter):
    """A minimal stub advertising image support only, for base-class behavior."""

    def capability(self) -> ModalityCapability:
        return ModalityCapability(image=True)

    def _encode_text(self, text: str) -> dict[str, Any]:
        return {"t": text}

    def _encode_image(self, block: ImageBlock) -> dict[str, Any]:
        return {"img": block.source.media_type}

    def _decode_block(self, native: Any) -> ContentBlock | None:
        if isinstance(native, dict) and "t" in native:
            return TextBlock(text=str(native["t"]))
        return None


class TestModalityCapability(unittest.TestCase):
    def test_text_always_supported(self) -> None:
        assert ModalityCapability().supports("text") is True

    def test_flags_gate_non_text(self) -> None:
        cap = ModalityCapability(image=True, audio=False, file=True)
        assert cap.supports("image") is True
        assert cap.supports("audio") is False
        assert cap.supports("file") is True

    def test_unknown_modality_unsupported(self) -> None:
        assert ModalityCapability(image=True).supports("tool_result") is False


class TestAdapterBase(unittest.TestCase):
    def test_text_and_supported_image_encode(self) -> None:
        adapter = _ImageOnlyAdapter()
        parts = adapter.encode_blocks(
            [
                TextBlock(text="hi"),
                ImageBlock(source=MediaHandle(media_type="image/png", data=b"d")),
            ]
        )
        assert parts == [{"t": "hi"}, {"img": "image/png"}]

    def test_unsupported_modality_raises_by_default(self) -> None:
        adapter = _ImageOnlyAdapter()
        with self.assertRaises(UnsupportedModalityError):
            adapter.encode_blocks([AudioBlock(source=MediaHandle(media_type="audio/wav", uri="u"))])

    def test_unsupported_modality_degrades_to_text(self) -> None:
        adapter = _ImageOnlyAdapter()
        parts = adapter.encode_blocks(
            [AudioBlock(source=MediaHandle(media_type="audio/wav", uri="u"), transcript="hello")],
            degrade=True,
        )
        assert parts == [{"t": "hello"}]

    def test_degraded_block_without_caption_uses_placeholder(self) -> None:
        adapter = _ImageOnlyAdapter()
        parts = adapter.encode_blocks(
            [AudioBlock(source=MediaHandle(media_type="audio/wav", uri="u"))], degrade=True
        )
        assert parts == [{"t": "[audio content omitted]"}]

    def test_encode_rejects_non_block(self) -> None:
        with self.assertRaises(TypeError):
            _ImageOnlyAdapter().encode_blocks(["nope"])  # type: ignore[list-item]

    def test_decode_bare_string_is_text_block(self) -> None:
        assert _ImageOnlyAdapter().decode_blocks("plain") == (TextBlock(text="plain"),)


class TestOpenAICompatibleAdapter(unittest.TestCase):
    def test_inline_image_becomes_data_uri(self) -> None:
        adapter = OpenAICompatibleMultimodalAdapter()
        part = adapter.encode_blocks(
            [ImageBlock(source=MediaHandle(media_type="image/png", data=b"px"))]
        )[0]
        assert part["type"] == "image_url"
        assert part["image_url"]["url"].startswith("data:image/png;base64,")

    def test_referenced_image_passes_url(self) -> None:
        adapter = OpenAICompatibleMultimodalAdapter()
        part = adapter.encode_blocks(
            [ImageBlock(source=MediaHandle(media_type="image/png", uri="https://h/x.png"))]
        )[0]
        assert part["image_url"]["url"] == "https://h/x.png"

    def test_image_round_trips_inline_bytes(self) -> None:
        adapter = OpenAICompatibleMultimodalAdapter()
        original = ImageBlock(source=MediaHandle(media_type="image/png", data=b"px"))
        decoded = adapter.decode_blocks(adapter.encode_blocks([original]))
        assert isinstance(decoded[0], ImageBlock)
        assert decoded[0].source.data == b"px"

    def test_audio_supported_here(self) -> None:
        adapter = OpenAICompatibleMultimodalAdapter()
        part = adapter.encode_blocks(
            [AudioBlock(source=MediaHandle(media_type="audio/wav", data=b"aa"))]
        )[0]
        assert part["type"] == "input_audio"
        assert part["input_audio"]["format"] == "wav"


class TestAnthropicMessagesAdapter(unittest.TestCase):
    def test_inline_image_becomes_base64_source(self) -> None:
        adapter = AnthropicMessagesMultimodalAdapter()
        part = adapter.encode_blocks(
            [ImageBlock(source=MediaHandle(media_type="image/png", data=b"px"))]
        )[0]
        assert part["type"] == "image"
        assert part["source"]["type"] == "base64"
        assert part["source"]["media_type"] == "image/png"

    def test_file_becomes_document(self) -> None:
        adapter = AnthropicMessagesMultimodalAdapter()
        part = adapter.encode_blocks(
            [FileBlock(source=MediaHandle(media_type="application/pdf", uri="u"), filename="r.pdf")]
        )[0]
        assert part["type"] == "document"
        assert part["source"]["type"] == "url"

    def test_audio_is_gated_unsupported(self) -> None:
        adapter = AnthropicMessagesMultimodalAdapter()
        with self.assertRaises(UnsupportedModalityError):
            adapter.encode_blocks([AudioBlock(source=MediaHandle(media_type="audio/wav", uri="u"))])

    def test_audio_degrades_without_reaching_encode_hook(self) -> None:
        adapter = AnthropicMessagesMultimodalAdapter()
        parts = adapter.encode_blocks(
            [AudioBlock(source=MediaHandle(media_type="audio/wav", uri="u"), transcript="hi")],
            degrade=True,
        )
        assert parts == [{"type": "text", "text": "hi"}]

    def test_image_round_trips(self) -> None:
        adapter = AnthropicMessagesMultimodalAdapter()
        original = ImageBlock(source=MediaHandle(media_type="image/png", data=b"px"))
        decoded = adapter.decode_blocks(adapter.encode_blocks([original]))
        assert isinstance(decoded[0], ImageBlock)
        assert decoded[0].source.data == b"px"


if __name__ == "__main__":
    unittest.main()
