"""``ModerationPatterns`` — the word list and PII pattern the signal knots match against.

Part of the ``examples.content_moderation`` example.
"""

from __future__ import annotations

import re
from typing import ClassVar


class ModerationPatterns:
    """Fixed matching configuration shared by the profanity, PII and toxicity knots."""

    profanity: ClassVar[frozenset[str]] = frozenset({"badword", "spam", "offensive"})
    pii_pattern: ClassVar[re.Pattern[str]] = re.compile(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"  # email
        r"|\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b"  # phone
        r"|\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b"  # card
    )
