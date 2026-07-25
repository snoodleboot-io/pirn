"""``MarkdownLoader`` — decode Markdown to plain text using only stdlib (F25-S1).

Needs no optional backend: it decodes UTF-8 and, by default, strips the common
inline/block Markdown markers (headings, emphasis, inline code, list bullets,
and link syntax — keeping the link text) so downstream chunking sees prose
rather than syntax. The raw Markdown is preserved in metadata under ``raw`` for
callers that want the original.
"""

from __future__ import annotations

import re

from pirn_agents.specializations.document_processing.loaders.loaded_document import (
    LoadedDocument,
)
from pirn_agents.specializations.document_processing.loaders.loader import Loader


class MarkdownLoader(Loader):
    """Decode Markdown bytes to plain text, optionally stripping formatting."""

    def __init__(self, *, strip_formatting: bool = True) -> None:
        """Configure the loader.

        Args:
            strip_formatting: When ``True``, remove Markdown markers and keep
                only the human-readable text.
        """
        self._strip_formatting = strip_formatting

    async def load(self, data: bytes, *, source_id: str | None = None) -> LoadedDocument:
        """Decode the Markdown and return a normalized document.

        Args:
            data: The raw Markdown bytes (UTF-8).
            source_id: Optional identifier recorded on the document.

        Returns:
            A :class:`LoadedDocument` whose ``text`` is the (optionally
            de-formatted) content, with the original Markdown under
            ``metadata['raw']``.

        Raises:
            TypeError: If ``data`` is not bytes.
            ValueError: If the bytes are not valid UTF-8.
        """
        raw = self._require_bytes("MarkdownLoader", data)
        try:
            markdown = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(f"MarkdownLoader: bytes are not valid UTF-8: {exc}") from exc
        text = self._strip(markdown) if self._strip_formatting else markdown
        return LoadedDocument(
            text=text,
            metadata={"content_type": "text/markdown", "raw": markdown},
            source_id=source_id,
        )

    @staticmethod
    def _strip(markdown: str) -> str:
        """Remove the common Markdown markers, keeping the readable text."""
        text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", markdown)  # images
        text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)  # links -> text
        text = re.sub(r"`{1,3}([^`]*)`{1,3}", r"\1", text)  # inline/fenced code ticks
        text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.MULTILINE)  # headings
        text = re.sub(r"[*_]{1,3}([^*_]+)[*_]{1,3}", r"\1", text)  # emphasis
        text = re.sub(r"^\s{0,3}[-*+]\s+", "", text, flags=re.MULTILINE)  # bullets
        text = re.sub(r"^\s{0,3}>\s?", "", text, flags=re.MULTILINE)  # blockquotes
        return text.strip()
