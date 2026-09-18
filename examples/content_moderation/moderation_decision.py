"""``ModerationDecision`` — the final moderation verdict.

Part of the ``examples.content_moderation`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModerationDecision:
    """Final moderation verdict."""

    action: str  # "allow" | "warn" | "block"
    reason: str
    score: float
