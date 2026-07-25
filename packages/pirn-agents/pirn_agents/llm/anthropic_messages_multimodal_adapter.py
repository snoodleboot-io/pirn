"""``AnthropicMessagesMultimodalAdapter`` — multimodal shaping for the Messages API (F15-S2).

Encodes neutral content blocks into the Messages-API content blocks and back. A
peer of
:class:`pirn_agents.llm.openai_compatible_multimodal_adapter.OpenAICompatibleMultimodalAdapter`
demonstrating the base's provider-neutrality: the same neutral blocks map onto a
*distinct* wire shape (a typed ``source`` object rather than a URL string), and
this wire format carries no audio part — so an audio block trips the
capability-gated unsupported-modality path.

Per-format paths: a referenced :class:`~pirn_agents.types.media_handle.MediaHandle`
becomes a ``{"type": "url", "url": ...}`` source; an inline payload becomes a
``{"type": "base64", "media_type": ..., "data": ...}`` source. Native shapes:

* text     — ``{"type": "text", "text": ...}``
* image    — ``{"type": "image", "source": {...}}``
* document — ``{"type": "document", "source": {...}}`` (file/document blocks)
"""

from __future__ import annotations

import base64
from typing import Any

from pirn_agents.llm.modality_capability import ModalityCapability
from pirn_agents.llm.multimodal_adapter import MultimodalAdapter
from pirn_agents.types.audio_block import AudioBlock
from pirn_agents.types.content_block import ContentBlock
from pirn_agents.types.file_block import FileBlock
from pirn_agents.types.image_block import ImageBlock
from pirn_agents.types.media_handle import MediaHandle
from pirn_agents.types.text_block import TextBlock


class AnthropicMessagesMultimodalAdapter(MultimodalAdapter):
    """Neutral ↔ Messages-API multimodal content-block translation."""

    def capability(self) -> ModalityCapability:
        """Advertise image and file (document) support; audio is not carried."""
        return ModalityCapability(image=True, audio=False, file=True)

    def _encode_text(self, text: str) -> dict[str, Any]:
        return {"type": "text", "text": text}

    def _encode_image(self, block: ImageBlock) -> dict[str, Any]:
        return {"type": "image", "source": self._source_of(block.source)}

    def _encode_audio(self, block: AudioBlock) -> dict[str, Any]:
        # Unreachable: capability() reports audio unsupported, so the base gates
        # audio blocks before dispatch. Present to satisfy the interface.
        raise NotImplementedError("Messages API wire format carries no audio part")

    def _encode_file(self, block: FileBlock) -> dict[str, Any]:
        return {"type": "document", "source": self._source_of(block.source)}

    def _decode_block(self, native: Any) -> ContentBlock | None:
        if not isinstance(native, dict):
            return None
        part_type = native.get("type")
        if part_type == "text":
            return TextBlock(text=str(native.get("text", "")))
        if part_type == "image":
            return ImageBlock(source=self._handle_of(native.get("source") or {}, "image/*"))
        if part_type == "document":
            return FileBlock(
                source=self._handle_of(native.get("source") or {}, "application/octet-stream")
            )
        return None

    @staticmethod
    def _source_of(handle: MediaHandle) -> dict[str, Any]:
        """Shape a Messages-API ``source`` object from a media handle."""
        if handle.data is not None:
            return {
                "type": "base64",
                "media_type": handle.media_type,
                "data": base64.b64encode(handle.data).decode("ascii"),
            }
        return {"type": "url", "url": handle.uri}

    @staticmethod
    def _handle_of(source: dict[str, Any], fallback_media_type: str) -> MediaHandle:
        """Rebuild a :class:`MediaHandle` from a Messages-API ``source`` object."""
        if source.get("type") == "base64":
            return MediaHandle(
                media_type=str(source.get("media_type") or fallback_media_type),
                data=base64.b64decode(str(source.get("data", ""))),
            )
        return MediaHandle(media_type=fallback_media_type, uri=str(source.get("url", "")))
