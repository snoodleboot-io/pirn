"""``DocxLoader`` — extract paragraph text from a .docx via the lazy ``docx`` extra (F25-S1).

Wraps ``python-docx`` (imported as ``docx``, lazily through
:func:`~pirn_agents._require._require`). Joins every paragraph's text into one
normalized :class:`LoadedDocument`. Embedded images and complex objects are out
of scope until F15 (see :class:`Loader`).
"""

from __future__ import annotations

import io

from pirn_agents._require import _require
from pirn_agents.specializations.document_processing.loaders.loaded_document import (
    LoadedDocument,
)
from pirn_agents.specializations.document_processing.loaders.loader import Loader


class DocxLoader(Loader):
    """Extract paragraph text from a Word ``.docx`` document."""

    def __init__(self, *, paragraph_separator: str = "\n") -> None:
        """Configure the loader.

        Args:
            paragraph_separator: String joining consecutive paragraphs.
        """
        self._paragraph_separator = paragraph_separator

    async def load(self, data: bytes, *, source_id: str | None = None) -> LoadedDocument:
        """Extract paragraph text and return a normalized document.

        Args:
            data: The raw ``.docx`` bytes.
            source_id: Optional identifier recorded on the document.

        Returns:
            A :class:`LoadedDocument` whose ``text`` is the paragraph-joined
            content and whose metadata carries ``content_type`` and
            ``paragraph_count``.

        Raises:
            TypeError: If ``data`` is not bytes.
            ValueError: If the bytes are not a parseable ``.docx``.
        """
        raw = self._require_bytes("DocxLoader", data)
        docx = _require("docx", "docx")
        try:
            document = docx.Document(io.BytesIO(raw))
            paragraphs = [paragraph.text for paragraph in document.paragraphs]
        except Exception as exc:
            raise ValueError(f"DocxLoader: could not parse .docx bytes: {exc}") from exc
        text = self._paragraph_separator.join(paragraphs)
        return LoadedDocument(
            text=text,
            metadata={
                "content_type": (
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                ),
                "paragraph_count": len(paragraphs),
            },
            source_id=source_id,
        )
