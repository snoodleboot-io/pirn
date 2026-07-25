"""``ImageBlock`` — the image variant of the content-block union (F15-S1)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn_agents.types.content_block import ContentBlock
from pirn_agents.types.media_handle import MediaHandle


@dataclass(frozen=True)
class ImageBlock(ContentBlock):
    """An image carried by reference or inline via a :class:`MediaHandle`.

    Attributes
    ----------
    source:
        The image payload pointer (URL/handle or inline bytes).
    alt_text:
        Optional textual description used as the block's text projection and as
        a graceful-degradation caption for text-only providers.
    """

    source: MediaHandle
    alt_text: str | None = None

    def __post_init__(self) -> None:
        """Validate the payload pointer and optional caption.

        Raises:
            TypeError: If ``source`` is not a :class:`MediaHandle`, or
                ``alt_text`` is neither a string nor ``None``.
        """
        if not isinstance(self.source, MediaHandle):
            raise TypeError(
                f"ImageBlock: source must be a MediaHandle, got {type(self.source).__name__}"
            )
        if self.alt_text is not None and not isinstance(self.alt_text, str):
            raise TypeError(
                f"ImageBlock: alt_text must be a str or None, got {type(self.alt_text).__name__}"
            )

    @property
    def modality(self) -> str:
        """Return the neutral modality tag ``"image"``."""
        return "image"

    @property
    def as_text(self) -> str:
        """Return :attr:`alt_text` if present, else the empty string."""
        return self.alt_text or ""

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "modality": "image",
            "source": self.source._pirn_audit_dict(),
            "alt_text": self.alt_text,
        }
