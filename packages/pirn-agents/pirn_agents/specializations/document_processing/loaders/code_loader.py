"""``CodeLoader`` — decode source-code bytes to text using only stdlib (F25-S1).

Needs no optional backend: it decodes UTF-8 and preserves the source verbatim
(indentation and line breaks matter for code), recording the line count and an
optional caller-supplied ``language`` label in metadata. Pair it with the
code-aware chunking strategy (F25-S2) to split on structural boundaries.
"""

from __future__ import annotations

from pirn_agents.specializations.document_processing.loaders.loaded_document import (
    LoadedDocument,
)
from pirn_agents.specializations.document_processing.loaders.loader import Loader


class CodeLoader(Loader):
    """Decode source-code bytes to verbatim text with line-count metadata."""

    def __init__(self, *, language: str | None = None) -> None:
        """Configure the loader.

        Args:
            language: Optional language label (e.g. ``"python"``) recorded in
                the document metadata; loaders do not infer it from content.
        """
        self._language = language

    async def load(self, data: bytes, *, source_id: str | None = None) -> LoadedDocument:
        """Decode the source verbatim and return a normalized document.

        Args:
            data: The raw source-code bytes (UTF-8).
            source_id: Optional identifier recorded on the document.

        Returns:
            A :class:`LoadedDocument` whose ``text`` is the verbatim source and
            whose metadata carries ``content_type``, ``line_count``, and
            (when set) ``language``.

        Raises:
            TypeError: If ``data`` is not bytes.
            ValueError: If the bytes are not valid UTF-8.
        """
        raw = self._require_bytes("CodeLoader", data)
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(f"CodeLoader: bytes are not valid UTF-8: {exc}") from exc
        metadata: dict[str, object] = {
            "content_type": "text/x-source",
            "line_count": text.count("\n") + 1 if text else 0,
        }
        if self._language is not None:
            metadata["language"] = self._language
        return LoadedDocument(text=text, metadata=metadata, source_id=source_id)
