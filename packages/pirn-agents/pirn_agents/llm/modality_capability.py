"""``ModalityCapability`` — the modalities a provider can encode/decode (F15-S2).

A small, provider-neutral value object describing which content-block modalities
a provider's wire format supports. It is the capability surface the multimodal
codec probes before encoding: a block whose modality is not advertised is either
projected to text (graceful degradation) or rejected with a clear
:class:`~pirn_agents.exceptions.unsupported_modality_error.UnsupportedModalityError`.

Text is always supported (every LLM accepts text), so it has no flag. Each
provider decides its own flags and owns the wire shaping behind its adapter.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModalityCapability:
    """Flags describing which non-text modalities a provider supports.

    Attributes
    ----------
    image:
        Whether the provider accepts image content blocks.
    audio:
        Whether the provider accepts audio content blocks.
    file:
        Whether the provider accepts file/document content blocks.
    """

    image: bool = False
    audio: bool = False
    file: bool = False

    def supports(self, modality: str) -> bool:
        """Return whether ``modality`` is supported.

        Text is always supported; the other tags consult the matching flag; any
        unknown tag (e.g. ``"tool_result"``) is treated as unsupported by this
        wire-modality probe.
        """
        if modality == "text":
            return True
        if modality == "image":
            return self.image
        if modality == "audio":
            return self.audio
        if modality == "file":
            return self.file
        return False
