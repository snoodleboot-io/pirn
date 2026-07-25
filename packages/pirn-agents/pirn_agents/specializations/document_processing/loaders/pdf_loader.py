"""``PdfLoader`` — extract text from a PDF via the lazy ``pdf`` extra (F25-S1).

Wraps ``pypdf`` (imported lazily through
:func:`~pirn_agents._require._require`, so importing this module never pulls the
backend). Concatenates the extracted text of every page into one normalized
:class:`LoadedDocument`, recording the page count in metadata. Multimodal PDF
content (embedded images) is out of scope until F15 (see :class:`Loader`).
"""

from __future__ import annotations

import io

from pirn_agents._require import _require
from pirn_agents.specializations.document_processing.loaders.loaded_document import (
    LoadedDocument,
)
from pirn_agents.specializations.document_processing.loaders.loader import Loader


class PdfLoader(Loader):
    """Extract page text from a PDF into a :class:`LoadedDocument`."""

    def __init__(self, *, page_separator: str = "\n\n") -> None:
        """Configure the loader.

        Args:
            page_separator: String joining consecutive pages' extracted text.
        """
        self._page_separator = page_separator

    async def load(self, data: bytes, *, source_id: str | None = None) -> LoadedDocument:
        """Extract text from every page and return a normalized document.

        Args:
            data: The raw PDF bytes.
            source_id: Optional identifier recorded on the document.

        Returns:
            A :class:`LoadedDocument` whose ``text`` is the page-joined content
            and whose metadata carries ``content_type`` and ``page_count``.

        Raises:
            TypeError: If ``data`` is not bytes.
            ValueError: If the bytes are not a parseable PDF.
        """
        raw = self._require_bytes("PdfLoader", data)
        pypdf = _require("pdf", "pypdf")
        try:
            reader = pypdf.PdfReader(io.BytesIO(raw))
            pages = [(page.extract_text() or "") for page in reader.pages]
        except Exception as exc:
            raise ValueError(f"PdfLoader: could not parse PDF bytes: {exc}") from exc
        text = self._page_separator.join(pages)
        return LoadedDocument(
            text=text,
            metadata={"content_type": "application/pdf", "page_count": len(pages)},
            source_id=source_id,
        )
