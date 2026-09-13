"""``LLMProviderMultimodalMixin`` — F15-S2 multimodal capability surface for HTTP LLM providers.

Extracted from :class:`~pirn_agents.llm.base_llm_provider.BaseLLMProvider` (PIR-856,
SRP) to keep that orchestrator under one screenful of responsibility. This
mixin owns the three-method multimodal contract
(:meth:`modality_capability`/:meth:`encode_content`/:meth:`decode_content`) and
the ``_multimodal_adapter`` hook providers with native media support override;
the base text-only behaviour needs no adapter at all.

It contributes no ``__init__`` of its own and is always combined with
:class:`~pirn_agents.llm.base_llm_provider.BaseLLMProvider`, never instantiated
directly.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn_agents.exceptions.unsupported_modality_error import UnsupportedModalityError
from pirn_agents.llm.modality_capability import ModalityCapability
from pirn_agents.llm.multimodal_adapter import MultimodalAdapter
from pirn_agents.types.content.content_block import ContentBlock


class LLMProviderMultimodalMixin:
    """Multimodal encode/decode surface for :class:`BaseLLMProvider` (F15-S2)."""

    def modality_capability(self) -> ModalityCapability:
        """Return which content-block modalities this provider can encode.

        Delegates to the provider's multimodal adapter; a bare base provider
        that supplies no adapter is text-only, so an empty capability (text
        implicit, no image/audio/file) is returned.
        """
        adapter = self._multimodal_adapter()
        return adapter.capability() if adapter is not None else ModalityCapability()

    def encode_content(
        self, blocks: Sequence[ContentBlock], *, degrade: bool = False
    ) -> list[dict[str, Any]]:
        """Encode neutral content ``blocks`` into this provider's native parts.

        Providers with a multimodal adapter delegate to it (capability-gated,
        per-format shaping). A text-only base provider accepts text blocks and,
        with ``degrade=True``, projects any non-text block to a text part; else
        an unsupported block raises.

        Raises:
            UnsupportedModalityError: If a non-text block is present, this is a
                text-only provider, and ``degrade`` is ``False``.
        """
        adapter = self._multimodal_adapter()
        if adapter is not None:
            return adapter.encode_blocks(blocks, degrade=degrade)
        parts: list[dict[str, Any]] = []
        for block in blocks:
            if block.modality == "text":
                parts.append({"type": "text", "text": block.as_text})
            elif degrade:
                text = block.as_text or f"[{block.modality} content omitted]"
                parts.append({"type": "text", "text": text})
            else:
                raise UnsupportedModalityError(block.modality, type(self).__name__)
        return parts

    def decode_content(self, native_content: Any) -> tuple[ContentBlock, ...]:
        """Decode a provider-native content value back into neutral blocks.

        Providers with a multimodal adapter delegate to it; a text-only base
        provider returns a single text block (string input) or nothing.
        """
        adapter = self._multimodal_adapter()
        if adapter is not None:
            return adapter.decode_blocks(native_content)
        if isinstance(native_content, str):
            from pirn_agents.types.content.text_block import TextBlock

            return (TextBlock(text=native_content),)
        return ()

    def _multimodal_adapter(self) -> MultimodalAdapter | None:
        """Return this provider's multimodal adapter, or ``None`` if text-only.

        The base is text-only and returns ``None``; providers whose wire format
        carries media override this to return their adapter.
        """
        return None
