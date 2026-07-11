"""``_TextExtractor`` — zero-dependency HTML-to-text extraction.

A small :class:`~html.parser.HTMLParser` subclass that drops ``<script>`` and
``<style>`` bodies, emits text for everything else, inserts newlines around block
elements, and lets the stdlib parser unescape entities. It has no third-party
dependency, so it never widens the base wheel.
"""

from __future__ import annotations

from html.parser import HTMLParser


class _TextExtractor(HTMLParser):
    """Collect visible text from an HTML document, skipping script/style."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Enter skip mode for script/style; add spacing for block elements."""
        if tag in ("script", "style"):
            self._skip_depth += 1
        elif tag in ("p", "br", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"):
            self._chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        """Leave skip mode when a script/style element closes."""
        if tag in ("script", "style") and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        """Collect text unless inside a skipped element."""
        if self._skip_depth == 0:
            self._chunks.append(data)

    def text(self) -> str:
        """Return the collected text with runs of blank lines/space collapsed."""
        raw = "".join(self._chunks)
        lines = [" ".join(line.split()) for line in raw.splitlines()]
        collapsed = [line for line in lines if line]
        return "\n".join(collapsed)
