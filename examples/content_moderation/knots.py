"""Knot implementations for the content moderation tapestry.

These are referenced by dotted path from the YAML definition.
"""

from __future__ import annotations

import re

from pirn.core.knot_factory import KnotFactory

from examples.content_moderation.content_flags import ContentFlags
from examples.content_moderation.moderation_decision import ModerationDecision
from examples.content_moderation.moderation_patterns import ModerationPatterns


@KnotFactory.knot
def normalise(raw_text: str) -> str:
    """Strip and lowercase the input text."""
    return raw_text.strip().lower()


@KnotFactory.knot
def detect_language(text: str) -> str:
    """Detect language from character set (stub: returns 'en' or 'unknown')."""
    ascii_ratio = sum(1 for c in text if ord(c) < 128) / max(len(text), 1)
    return "en" if ascii_ratio > 0.85 else "unknown"


@KnotFactory.knot
def check_profanity(text: str) -> bool:
    """Return True if the text contains known profanity."""
    words = set(re.findall(r"\w+", text))
    return bool(words & ModerationPatterns.profanity)


@KnotFactory.knot
def check_pii(text: str) -> bool:
    """Return True if the text contains personally identifiable information."""
    return bool(ModerationPatterns.pii_pattern.search(text))


@KnotFactory.knot
def score_toxicity(text: str) -> float:
    """Compute a simple heuristic toxicity score (0.0 - 1.0)."""
    bad_words = sum(
        1 for w in re.findall(r"\w+", text) if w in ModerationPatterns.profanity
    )
    caps_ratio = sum(1 for c in text if c.isupper()) / max(len(text), 1)
    return min(1.0, bad_words * 0.4 + caps_ratio * 0.3)


@KnotFactory.knot
def classify(
    has_profanity: bool,
    has_pii: bool,
    toxicity_score: float,
    language: str,
) -> ContentFlags:
    """Combine individual signals into a structured ContentFlags record."""
    return ContentFlags(
        has_profanity=has_profanity,
        has_pii=has_pii,
        toxicity_score=toxicity_score,
        language=language,
    )


@KnotFactory.knot
def decide(flags: ContentFlags) -> ModerationDecision:
    """Apply moderation policy and return a final decision."""
    if flags.has_pii:
        return ModerationDecision("block", "PII detected", flags.toxicity_score)
    if flags.toxicity_score >= 0.7 or flags.has_profanity:
        return ModerationDecision(
            "warn", "High toxicity or profanity", flags.toxicity_score
        )
    if flags.language == "unknown":
        return ModerationDecision(
            "warn", "Language not recognised", flags.toxicity_score
        )
    return ModerationDecision("allow", "Passed all checks", flags.toxicity_score)


@KnotFactory.knot
def audit_log(raw_text: str, decision: ModerationDecision) -> str:
    """Emit an audit log entry and return a summary string."""
    summary = (
        f"[{decision.action.upper()}] "
        f"score={decision.score:.2f} reason={decision.reason!r} "
        f"text={raw_text[:40]!r}"
    )
    print(f"  [audit] {summary}")
    return summary
