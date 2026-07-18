"""``AudioBlock`` — the audio variant of the content-block union (F15-S1)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn_agents.types.content_block import ContentBlock
from pirn_agents.types.media_handle import MediaHandle


@dataclass(frozen=True)
class AudioBlock(ContentBlock):
    """An audio clip carried by reference or inline via a :class:`MediaHandle`.

    Attributes
    ----------
    source:
        The audio payload pointer (URL/handle or inline bytes).
    transcript:
        Optional transcript used as the block's text projection and as a
        graceful-degradation caption for text-only providers.
    """

    source: MediaHandle
    transcript: str | None = None

    def __post_init__(self) -> None:
        """Validate the payload pointer and optional transcript.

        Raises:
            TypeError: If ``source`` is not a :class:`MediaHandle`, or
                ``transcript`` is neither a string nor ``None``.
        """
        if not isinstance(self.source, MediaHandle):
            raise TypeError(
                f"AudioBlock: source must be a MediaHandle, got {type(self.source).__name__}"
            )
        if self.transcript is not None and not isinstance(self.transcript, str):
            raise TypeError(
                "AudioBlock: transcript must be a str or None, "
                f"got {type(self.transcript).__name__}"
            )

    @property
    def modality(self) -> str:
        """Return the neutral modality tag ``"audio"``."""
        return "audio"

    @property
    def as_text(self) -> str:
        """Return :attr:`transcript` if present, else the empty string."""
        return self.transcript or ""

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "modality": "audio",
            "source": self.source._pirn_audit_dict(),
            "transcript": self.transcript,
        }
