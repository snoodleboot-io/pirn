"""``OpenAICompatibleMultimodalAdapter`` — multimodal shaping for chat-completions (F15-S2).

Encodes neutral content blocks into the ``chat/completions`` multimodal content
parts many servers speak, and decodes them back. This is a *wire-protocol*
adapter, a peer of
:class:`pirn_agents.llm.anthropic_messages_multimodal_adapter.AnthropicMessagesMultimodalAdapter`;
it privileges no vendor.

Per-format paths (the "URLs vs base64" split): a referenced
:class:`~pirn_agents.types.media_handle.MediaHandle` is passed as its URL/handle,
while an inline payload is emitted as a ``data:`` base64 URI. Native shapes:

* text  — ``{"type": "text", "text": ...}``
* image — ``{"type": "image_url", "image_url": {"url": <url|data-uri>}}``
* audio — ``{"type": "input_audio", "input_audio": {"data": <b64>, "format": ...}}``
* file  — ``{"type": "file", "file": {"filename": ..., "file_data"|"file_url": ...}}``
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


class OpenAICompatibleMultimodalAdapter(MultimodalAdapter):
    """Neutral ↔ chat-completions multimodal content-part translation."""

    def capability(self) -> ModalityCapability:
        """Advertise image, audio, and file support for this wire format."""
        return ModalityCapability(image=True, audio=True, file=True)

    def _encode_text(self, text: str) -> dict[str, Any]:
        return {"type": "text", "text": text}

    def _encode_image(self, block: ImageBlock) -> dict[str, Any]:
        return {"type": "image_url", "image_url": {"url": self._url_or_data_uri(block.source)}}

    def _encode_audio(self, block: AudioBlock) -> dict[str, Any]:
        source = block.source
        if source.data is not None:
            payload = {
                "data": base64.b64encode(source.data).decode("ascii"),
                "format": self._format_of(source.media_type),
            }
        else:
            payload = {"url": source.uri, "format": self._format_of(source.media_type)}
        return {"type": "input_audio", "input_audio": payload}

    def _encode_file(self, block: FileBlock) -> dict[str, Any]:
        source = block.source
        file_part: dict[str, Any] = {"filename": block.filename}
        if source.data is not None:
            file_part["file_data"] = self._url_or_data_uri(source)
        else:
            file_part["file_url"] = source.uri
        return {"type": "file", "file": file_part}

    def _decode_block(self, native: Any) -> ContentBlock | None:
        if not isinstance(native, dict):
            return None
        part_type = native.get("type")
        if part_type == "text":
            return TextBlock(text=str(native.get("text", "")))
        if part_type == "image_url":
            url = (native.get("image_url") or {}).get("url", "")
            return ImageBlock(source=self._handle_from_url(url, "image/*"))
        if part_type == "input_audio":
            audio = native.get("input_audio") or {}
            if "url" in audio:
                return AudioBlock(
                    source=MediaHandle(media_type="audio/*", uri=str(audio.get("url")))
                )
            data = base64.b64decode(str(audio.get("data", "")))
            fmt = str(audio.get("format", "wav"))
            return AudioBlock(source=MediaHandle(media_type=f"audio/{fmt}", data=data))
        if part_type == "file":
            file_part = native.get("file") or {}
            filename = file_part.get("filename")
            if "file_url" in file_part:
                source = MediaHandle(
                    media_type="application/octet-stream", uri=str(file_part.get("file_url"))
                )
            else:
                source = self._handle_from_url(
                    str(file_part.get("file_data", "")), "application/octet-stream"
                )
            return FileBlock(source=source, filename=filename)
        return None

    @staticmethod
    def _url_or_data_uri(handle: MediaHandle) -> str:
        """Return the handle's URL, or a ``data:`` base64 URI for inline bytes."""
        if handle.data is not None:
            encoded = base64.b64encode(handle.data).decode("ascii")
            return f"data:{handle.media_type};base64,{encoded}"
        return handle.uri or ""

    @staticmethod
    def _handle_from_url(url: str, fallback_media_type: str) -> MediaHandle:
        """Rebuild a :class:`MediaHandle` from a URL or ``data:`` base64 URI."""
        if url.startswith("data:") and ";base64," in url:
            header, encoded = url.split(";base64,", 1)
            media_type = header[len("data:") :] or fallback_media_type
            return MediaHandle(media_type=media_type, data=base64.b64decode(encoded))
        return MediaHandle(media_type=fallback_media_type, uri=url)

    @staticmethod
    def _format_of(media_type: str) -> str:
        """Derive a bare audio format token (e.g. ``"wav"``) from a media type."""
        return media_type.split("/", 1)[1] if "/" in media_type else media_type
