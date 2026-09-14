"""``RetryState`` — the value threaded through the parse-retry loop.

Internal API. See ``retry_on_parse_failure_loop.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RetryState:
    """One attempt's worth of accumulated parse-retry state.

    Frozen; ``fold`` returns a new instance rather than mutating, matching
    every other ``LoopSubTapestry`` state in this package.

    Attributes:
        prompt: The prompt to send on the next attempt — the original prompt
            on the first attempt, or the original prompt plus the previous
            error on a retry.
        parsed_value: The successfully parsed value, or ``None`` before the
            first success.
        succeeded: Whether ``parsed_value`` is a real, parsed result.
        last_error: The most recent parse failure's message, or the initial
            sentinel when no attempt has run yet.
        attempts: How many attempts have completed.
    """

    prompt: str
    parsed_value: Any
    succeeded: bool
    last_error: str
    attempts: int
