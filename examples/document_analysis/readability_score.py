"""``ReadabilityScore`` — Flesch reading-ease approximation and grade level.

Part of the ``examples.document_analysis`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ReadabilityScore:
    grade_level: float  # US grade level approximation
    ease: float  # Flesch reading-ease 0-100
    avg_sentence_length: float
    avg_word_length: float
