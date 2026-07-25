"""``HtmlLoader`` — extract visible text from HTML via the lazy ``html`` extra (F25-S1).

Wraps ``beautifulsoup4`` (imported lazily through
:func:`~pirn_agents._require._require`) with the stdlib ``html.parser`` backend
so no compiled parser (lxml) is required. Strips ``<script>`` and ``<style>``
subtrees, collapses the remaining text, and records the document title in
metadata.
"""

from __future__ import annotations

from pirn_agents._require import _require
from pirn_agents.specializations.document_processing.loaders.loaded_document import (
    LoadedDocument,
)
from pirn_agents.specializations.document_processing.loaders.loader import Loader


class HtmlLoader(Loader):
    """Extract visible text and the title from an HTML document."""

    def __init__(self, *, separator: str = "\n") -> None:
        """Configure the loader.

        Args:
            separator: String inserted between text runs of adjacent elements.
        """
        self._separator = separator

    async def load(self, data: bytes, *, source_id: str | None = None) -> LoadedDocument:
        """Strip markup and return the visible text as a normalized document.

        Args:
            data: The raw HTML bytes.
            source_id: Optional identifier recorded on the document.

        Returns:
            A :class:`LoadedDocument` whose ``text`` is the visible content and
            whose metadata carries ``content_type`` and (when present) ``title``.

        Raises:
            TypeError: If ``data`` is not bytes.
        """
        raw = self._require_bytes("HtmlLoader", data)
        bs4 = _require("html", "bs4")
        soup = bs4.BeautifulSoup(raw, "html.parser")
        for tag in soup(["script", "style"]):
            tag.decompose()
        text = soup.get_text(separator=self._separator).strip()
        metadata: dict[str, object] = {"content_type": "text/html"}
        if soup.title is not None and soup.title.string:
            metadata["title"] = soup.title.string.strip()
        return LoadedDocument(text=text, metadata=metadata, source_id=source_id)
