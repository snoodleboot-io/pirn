"""``_JsonExtractorState`` — the value threaded through the extraction-retry loop.

Internal API. See ``_json_extractor_loop.py``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class _JsonExtractorState:
    """One attempt's worth of accumulated JSON-extraction state.

    Frozen; ``fold`` returns a new instance rather than mutating, matching
    every other ``LoopSubTapestry`` state in this package.

    Attributes:
        prior_error: The error to feed back into the next attempt's system
            prompt for self-correction, or the empty string before any
            attempt.
        result: The successfully parsed mapping, or ``None`` before success.
        last_error: The most recent attempt's error message, or the initial
            sentinel when no attempt has run yet.
        attempts: How many attempts have completed.
    """

    prior_error: str
    result: Mapping[str, Any] | None
    last_error: str
    attempts: int
