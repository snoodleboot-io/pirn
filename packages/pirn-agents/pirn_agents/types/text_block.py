"""``TextBlock`` — the plain-text variant of the content-block union (F15-S1)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn_agents.types.content_block import ContentBlock


@dataclass(frozen=True)
class TextBlock(ContentBlock):
    """A run of plain text within a message body.

    Attributes
    ----------
    text:
        The literal text of this block.
    """

    text: str

    def __post_init__(self) -> None:
        """Validate that ``text`` is a string.

        Raises:
            TypeError: If ``text`` is not a string.
        """
        if not isinstance(self.text, str):
            raise TypeError(f"TextBlock: text must be a str, got {type(self.text).__name__}")

    @property
    def modality(self) -> str:
        """Return the neutral modality tag ``"text"``."""
        return "text"

    @property
    def as_text(self) -> str:
        """Return this block's text unchanged."""
        return self.text

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {"modality": "text", "text": self.text}
