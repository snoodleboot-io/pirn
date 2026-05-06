"""Tiny HTML-to-plain-text helper used by ``EpubFormat``."""

from __future__ import annotations

from html.parser import HTMLParser
from typing import ClassVar


class _HtmlStripper(HTMLParser):
    """Extract plain text from an HTML fragment."""

    _block_tags: ClassVar[frozenset[str]] = frozenset(
        {"p", "br", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6"}
    )

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._block_tags:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._block_tags - {"br"}:
            self._parts.append("\n")

    def text(self) -> str:
        joined = "".join(self._parts)
        return "\n".join(line.strip() for line in joined.splitlines() if line.strip())
