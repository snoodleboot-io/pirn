"""``TextNormaliser`` — cleans a document and pre-computes downstream tokens.

Part of the ``examples.document_analysis`` example.
"""

from __future__ import annotations

import re
from typing import Any, ClassVar

from pirn.core.knot import Knot

from examples.document_analysis.document import Document
from examples.document_analysis.normalised_text import NormalisedText


class TextNormaliser(Knot):
    """Cleans a document and pre-computes tokens for downstream analysers.

    Strips HTML tags, collapses whitespace, lower-cases for token lists,
    and splits into sentences and words.  The original case is preserved
    in ``body`` for display; ``words`` is the lower-cased token list.
    """

    _html_tag: ClassVar[re.Pattern[str]] = re.compile(r"<[^>]+>")
    _punct: ClassVar[re.Pattern[str]] = re.compile(r"[^a-z0-9\s]")
    _sent_split: ClassVar[re.Pattern[str]] = re.compile(r"(?<=[.!?])\s+")

    async def process(self, document: Document, **_: Any) -> NormalisedText:
        clean = self._html_tag.sub(" ", document.body)
        clean = re.sub(r"\s+", " ", clean).strip()

        sentences = [s.strip() for s in self._sent_split.split(clean) if s.strip()]
        words = self._punct.sub("", clean.lower()).split()

        return NormalisedText(
            title=document.title,
            body=clean,
            words=words,
            sentences=sentences,
            word_count=len(words),
            sentence_count=max(len(sentences), 1),
        )
