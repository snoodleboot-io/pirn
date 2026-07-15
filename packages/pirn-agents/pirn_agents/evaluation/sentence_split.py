"""``split_sentences`` — naive backend-free sentence/claim splitter."""

from __future__ import annotations

import re

_SENTENCE_BOUNDARY = re.compile(r"[.!?]+")


def split_sentences(text: str) -> list[str]:
    """Split ``text`` into trimmed, non-empty sentence-like claims.

    Deliberately simple (no NLP backend): it breaks on runs of ``.``/``!``/``?``
    and drops empty fragments, which is enough to decompose an answer or a gold
    reference into per-claim units for faithfulness / recall scoring.

    Args:
        text: The passage to split.

    Returns:
        A list of trimmed sentence strings (empty when ``text`` has no
        non-whitespace content).

    Raises:
        TypeError: If ``text`` is not a ``str``.
    """
    if not isinstance(text, str):
        raise TypeError(f"split_sentences: text must be a str, got {type(text).__name__}")
    return [fragment.strip() for fragment in _SENTENCE_BOUNDARY.split(text) if fragment.strip()]
