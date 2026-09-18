"""A backtick code span found in markdown prose."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InlineCodeSpan:
    """The file line the span sits on and the text between its backticks."""

    line: int
    text: str
