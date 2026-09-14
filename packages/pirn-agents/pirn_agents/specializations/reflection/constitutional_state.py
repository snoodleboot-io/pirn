"""``ConstitutionalState`` — the value threaded through the revision loop.

Internal API. See ``constitutional_filter_loop.py``.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ConstitutionalState:
    """One revision attempt's worth of accumulated constitutional-review state.

    Frozen; ``fold`` returns a new instance rather than mutating, matching
    every other ``LoopSubTapestry`` state in this package.

    Attributes:
        principles_text: The bulleted principles list, rendered once and
            carried unchanged through every attempt.
        current_content: The response text being evaluated -- the original
            response before any attempt, or the LLM's revised text.
        attempts: How many evaluation attempts have completed.
        compliant: Whether the most recent evaluation reported ``COMPLIANT``.
    """

    principles_text: str
    current_content: str
    attempts: int
    compliant: bool
