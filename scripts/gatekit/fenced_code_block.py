"""A fenced code block extracted from a markdown file."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FencedCodeBlock:
    """The block's language tag, the file line of its first body line, and its body."""

    tag: str
    first_line: int
    source: str
