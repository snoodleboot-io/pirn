"""``ContentFlags`` — structured output from the classifier stage.

Part of the ``examples.content_moderation`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ContentFlags:
    """Structured output from the classifier stage."""

    has_profanity: bool
    has_pii: bool
    toxicity_score: float  # 0.0-1.0
    language: str
