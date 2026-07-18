"""``MultimodalAdapter`` — provider-neutral multimodal encode/decode base (F15-S2).

The multimodal counterpart to
:class:`pirn_agents.provider_adapter.ProviderAdapter`: it translates a sequence
of neutral :class:`~pirn_agents.types.content_block.ContentBlock` into one
provider's native message-content wire shape (and back), gated by a
:class:`~pirn_agents.llm.modality_capability.ModalityCapability` probe.

This base owns the cross-provider policy so concrete adapters stay tiny:

* **capability gating** — every block's modality is checked against
  :meth:`capability` before encoding;
* **graceful degradation** — with ``degrade=True`` an unsupported block is
  projected to a text part instead of failing;
* **fail-loud default** — otherwise an unsupported block raises
  :class:`~pirn_agents.exceptions.unsupported_modality_error.UnsupportedModalityError`.

Subclasses implement only the per-modality wire shaping hooks (``_encode_text``,
``_encode_image``, ``_encode_audio``, ``_encode_file`` and ``_decode_block``);
they never re-implement the gating or degradation logic. The adapter is opaque to
pydantic via :class:`pirn.core.pirn_opaque_value.PirnOpaqueValue`.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.exceptions.unsupported_modality_error import UnsupportedModalityError
from pirn_agents.llm.modality_capability import ModalityCapability
from pirn_agents.types.audio_block import AudioBlock
from pirn_agents.types.content_block import ContentBlock
from pirn_agents.types.file_block import FileBlock
from pirn_agents.types.image_block import ImageBlock


class MultimodalAdapter(PirnOpaqueValue):
    """Interface translating neutral content blocks to one provider's wire shape."""

    def capability(self) -> ModalityCapability:
        """Return the modalities this provider's wire format supports.

        Raises:
            NotImplementedError: Always, in the base; every adapter overrides it.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement capability()")

    @property
    def provider_label(self) -> str:
        """Return a human-readable label for error messages."""
        return type(self).__name__

    def encode_blocks(
        self, blocks: Sequence[ContentBlock], *, degrade: bool = False
    ) -> list[dict[str, Any]]:
        """Encode ``blocks`` into this provider's native content-part list.

        Text blocks always encode; a supported non-text modality is shaped by the
        matching hook; an unsupported one is projected to text when ``degrade`` is
        set, else raises.

        Raises:
            TypeError: If an item is not a :class:`ContentBlock`.
            UnsupportedModalityError: If a block's modality is unsupported and
                ``degrade`` is ``False``.
        """
        capability = self.capability()
        parts: list[dict[str, Any]] = []
        for block in blocks:
            if not isinstance(block, ContentBlock):
                raise TypeError(
                    f"{self.provider_label}: every item must be a ContentBlock, "
                    f"got {type(block).__name__}"
                )
            modality = block.modality
            if modality == "text":
                parts.append(self._encode_text(block.as_text))
                continue
            if not capability.supports(modality):
                if degrade:
                    parts.append(self._encode_text(self._degraded_text(block)))
                    continue
                raise UnsupportedModalityError(modality, self.provider_label)
            parts.append(self._encode_supported(block))
        return parts

    def decode_blocks(self, native_content: Any) -> tuple[ContentBlock, ...]:
        """Decode a provider-native content value back into neutral blocks.

        A bare string decodes to a single
        :class:`~pirn_agents.types.text_block.TextBlock`; a list of native parts
        is decoded item-by-item, skipping parts a subclass does not recognise.
        """
        from pirn_agents.types.text_block import TextBlock

        if isinstance(native_content, str):
            return (TextBlock(text=native_content),)
        decoded: list[ContentBlock] = []
        for native in native_content or []:
            block = self._decode_block(native)
            if block is not None:
                decoded.append(block)
        return tuple(decoded)

    def _encode_supported(self, block: ContentBlock) -> dict[str, Any]:
        """Dispatch a capability-checked non-text block to its wire-shaping hook."""
        if isinstance(block, ImageBlock):
            return self._encode_image(block)
        if isinstance(block, AudioBlock):
            return self._encode_audio(block)
        if isinstance(block, FileBlock):
            return self._encode_file(block)
        raise UnsupportedModalityError(block.modality, self.provider_label)

    @staticmethod
    def _degraded_text(block: ContentBlock) -> str:
        """Return the text a degraded (dropped) non-text block is replaced with."""
        return block.as_text or f"[{block.modality} content omitted]"

    # -- per-modality wire hooks (overridden by concrete adapters) -------

    def _encode_text(self, text: str) -> dict[str, Any]:
        """Shape a text run into this provider's native text part."""
        raise NotImplementedError(f"{type(self).__name__} must implement _encode_text()")

    def _encode_image(self, block: ImageBlock) -> dict[str, Any]:
        """Shape an image block into this provider's native image part."""
        raise NotImplementedError(f"{type(self).__name__} must implement _encode_image()")

    def _encode_audio(self, block: AudioBlock) -> dict[str, Any]:
        """Shape an audio block into this provider's native audio part."""
        raise NotImplementedError(f"{type(self).__name__} must implement _encode_audio()")

    def _encode_file(self, block: FileBlock) -> dict[str, Any]:
        """Shape a file block into this provider's native file part."""
        raise NotImplementedError(f"{type(self).__name__} must implement _encode_file()")

    def _decode_block(self, native: Any) -> ContentBlock | None:
        """Decode one native content part into a neutral block, or ``None``."""
        raise NotImplementedError(f"{type(self).__name__} must implement _decode_block()")
