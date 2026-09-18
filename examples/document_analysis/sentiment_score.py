"""``SentimentScore`` — lexicon sentiment label, normalised score and hit counts.

Part of the ``examples.document_analysis`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SentimentScore:
    label: str  # "positive" | "neutral" | "negative"
    score: float  # -1.0 … +1.0
    positive_hits: int
    negative_hits: int
