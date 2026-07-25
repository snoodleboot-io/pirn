"""``UnsupportedModalityError`` — a provider was asked to encode a modality it lacks."""

from __future__ import annotations


class UnsupportedModalityError(ValueError):
    """Raised when a content block's modality is not supported by a provider.

    A provider's :class:`~pirn_agents.llm.multimodal_adapter.MultimodalAdapter`
    raises this from ``encode_blocks`` when it is handed a block whose modality
    is absent from its :class:`~pirn_agents.llm.modality_capability.ModalityCapability`
    and graceful degradation was not requested — so a text-only provider fails
    loudly with an actionable message rather than silently dropping an image.

    Attributes
    ----------
    modality:
        The neutral modality tag that could not be encoded (e.g. ``"image"``).
    provider:
        A label for the adapter/provider that rejected the modality.
    """

    def __init__(self, modality: str, provider: str) -> None:
        self.modality = modality
        self.provider = provider
        super().__init__(
            f"{provider} does not support the {modality!r} modality; "
            "pass degrade=True to project it to text, or use a capable provider"
        )
