"""``Bm25Index`` — a pure-Python Okapi BM25 lexical index (OD-2).

A dependency-free lexical retriever: documents are tokenised, term/document
frequencies are accumulated, and queries are scored with the Okapi BM25 ranking
function. This resolves open decision OD-2 (lexical index with no external
dependency) and provides the sparse arm of the hybrid retriever.

Math:
    For query term :math:`t` and document :math:`d` of length :math:`|d|` in a
    corpus of :math:`N` documents with average length :math:`\\overline{d}`:

    .. math::

        \\text{idf}(t) = \\ln\\!\\left(1 + \\frac{N - n_t + 0.5}{n_t + 0.5}\\right)

        \\text{score}(d, q) = \\sum_{t \\in q} \\text{idf}(t) \\cdot
            \\frac{f_{t,d} (k_1 + 1)}{f_{t,d} + k_1 (1 - b + b\\,|d| / \\overline{d})}

    where :math:`f_{t,d}` is the frequency of :math:`t` in :math:`d`, and
    :math:`k_1`, :math:`b` are tuning parameters.
"""

from __future__ import annotations

import math
import re
from collections import Counter


class Bm25Index:
    """An in-memory Okapi BM25 index over tokenised documents."""

    def __init__(self, *, k1: float = 1.5, b: float = 0.75) -> None:
        """Initialise an empty index.

        Args:
            k1: Term-frequency saturation parameter (typically ~1.2-2.0).
            b: Length-normalisation parameter in ``[0, 1]``.

        Raises:
            ValueError: If ``k1`` is negative or ``b`` is outside ``[0, 1]``.
        """
        if k1 < 0:
            raise ValueError(f"k1 must be non-negative, got {k1!r}")
        if not 0.0 <= b <= 1.0:
            raise ValueError(f"b must be in [0, 1], got {b!r}")
        self._k1: float = k1
        self._b: float = b
        self._doc_ids: list[str] = []
        self._doc_terms: dict[str, Counter[str]] = {}
        self._doc_len: dict[str, int] = {}
        self._doc_freq: Counter[str] = Counter()

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Lowercase and split ``text`` into alphanumeric word tokens."""
        return re.findall(r"[a-z0-9]+", text.lower())

    def add(self, doc_id: str, text: str) -> None:
        """Add or replace a document in the index.

        Args:
            doc_id: Stable document id; re-adding an id replaces it.
            text: The document text to tokenise and index.
        """
        if doc_id in self._doc_terms:
            self._remove_stats(doc_id)
        else:
            self._doc_ids.append(doc_id)
        terms = Counter(self._tokenize(text))
        self._doc_terms[doc_id] = terms
        self._doc_len[doc_id] = sum(terms.values())
        for term in terms:
            self._doc_freq[term] += 1

    def _remove_stats(self, doc_id: str) -> None:
        """Retract the corpus statistics contributed by ``doc_id``."""
        for term in self._doc_terms[doc_id]:
            self._doc_freq[term] -= 1
            if self._doc_freq[term] <= 0:
                del self._doc_freq[term]

    def _average_length(self) -> float:
        """Return the mean document length, or ``0.0`` for an empty corpus."""
        if not self._doc_len:
            return 0.0
        return sum(self._doc_len.values()) / len(self._doc_len)

    def _idf(self, term: str, corpus_size: int) -> float:
        """Return the BM25 inverse document frequency of ``term``."""
        n_t = self._doc_freq.get(term, 0)
        return math.log(1.0 + (corpus_size - n_t + 0.5) / (n_t + 0.5))

    def search(self, query: str, *, top_k: int = 10) -> list[tuple[str, float]]:
        """Return the top ``top_k`` ``(doc_id, score)`` pairs for ``query``.

        Args:
            query: The free-text query to score against every document.
            top_k: Maximum number of results. Must be a positive integer.

        Returns:
            ``(doc_id, score)`` pairs ordered by descending BM25 score; documents
            scoring zero are omitted.

        Raises:
            ValueError: If ``top_k`` is not a positive integer.
        """
        if not isinstance(top_k, int) or top_k <= 0:
            raise ValueError(f"top_k must be a positive int, got {top_k!r}")
        corpus_size = len(self._doc_ids)
        if corpus_size == 0:
            return []
        query_terms = self._tokenize(query)
        avg_len = self._average_length()
        scored: list[tuple[str, float]] = []
        for doc_id in self._doc_ids:
            terms = self._doc_terms[doc_id]
            length = self._doc_len[doc_id]
            score = 0.0
            for term in query_terms:
                freq = terms.get(term, 0)
                if freq == 0:
                    continue
                idf = self._idf(term, corpus_size)
                denom = freq + self._k1 * (1.0 - self._b + self._b * length / avg_len)
                score += idf * (freq * (self._k1 + 1.0)) / denom
            if score > 0.0:
                scored.append((doc_id, score))
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return scored[:top_k]
