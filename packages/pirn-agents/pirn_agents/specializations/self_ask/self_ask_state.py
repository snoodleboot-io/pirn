"""``SelfAskState`` — the value threaded through the sub-answer loop.

Internal API. See ``self_ask_loop.py``.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SelfAskState:
    """One round's worth of accumulated Self-Ask sub-answer state.

    Frozen; ``fold`` returns a new instance rather than mutating, matching
    every other ``LoopSubTapestry`` state in this package.

    Attributes:
        subquestions: The full, fixed sub-question list decided before the
            loop started (decomposition already ran; this loop only answers
            each in turn).
        index: How many sub-questions have been answered so far — also the
            0-based index of the next sub-question to answer.
        subanswers: The answers collected so far, in sub-question order.
    """

    subquestions: tuple[str, ...]
    index: int
    subanswers: tuple[str, ...]
