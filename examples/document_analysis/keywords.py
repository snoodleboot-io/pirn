"""``Keywords`` — the ranked keyword terms extracted from a document.

Part of the ``examples.document_analysis`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Keywords:
    terms: list[tuple[str, float]]  # (word, tf-idf-ish score), descending
