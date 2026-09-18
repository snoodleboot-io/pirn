"""``NormalisedText`` — cleaned body plus pre-computed word and sentence tokens.

Part of the ``examples.document_analysis`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class NormalisedText:
    title: str
    body: str
    words: list[str]
    sentences: list[str]
    word_count: int
    sentence_count: int
