"""``FileBlock`` — the file/document variant of the content-block union (F15-S1)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn_agents.types.content_block import ContentBlock
from pirn_agents.types.media_handle import MediaHandle


@dataclass(frozen=True)
class FileBlock(ContentBlock):
    """A file/document carried by reference or inline via a :class:`MediaHandle`.

    Attributes
    ----------
    source:
        The file payload pointer (URL/handle or inline bytes).
    filename:
        Optional original filename used as the block's text projection and as a
        graceful-degradation caption for text-only providers.
    """

    source: MediaHandle
    filename: str | None = None

    def __post_init__(self) -> None:
        """Validate the payload pointer and optional filename.

        Raises:
            TypeError: If ``source`` is not a :class:`MediaHandle`, or
                ``filename`` is neither a string nor ``None``.
        """
        if not isinstance(self.source, MediaHandle):
            raise TypeError(
                f"FileBlock: source must be a MediaHandle, got {type(self.source).__name__}"
            )
        if self.filename is not None and not isinstance(self.filename, str):
            raise TypeError(
                f"FileBlock: filename must be a str or None, got {type(self.filename).__name__}"
            )

    @property
    def modality(self) -> str:
        """Return the neutral modality tag ``"file"``."""
        return "file"

    @property
    def as_text(self) -> str:
        """Return :attr:`filename` if present, else the empty string."""
        return self.filename or ""

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "modality": "file",
            "source": self.source._pirn_audit_dict(),
            "filename": self.filename,
        }
