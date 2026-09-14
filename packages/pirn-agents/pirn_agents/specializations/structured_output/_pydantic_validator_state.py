"""``PydanticValidatorState`` — the value threaded through the extraction-retry loop.

Internal API. See ``_pydantic_validator_loop.py``.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel


@dataclass(frozen=True)
class PydanticValidatorState:
    """One attempt's worth of accumulated extraction + validation state.

    Frozen; ``fold`` returns a new instance rather than mutating, matching
    every other ``LoopSubTapestry`` state in this package.

    Attributes:
        prior_error: The error to feed back into the next attempt's system
            prompt for self-correction, or the empty string before any
            attempt.
        validated: The successfully validated model instance, or ``None``
            before success.
        last_error: The most recent attempt's error message, or the initial
            sentinel when no attempt has run yet.
        attempts: How many attempts have completed.
    """

    prior_error: str
    validated: BaseModel | None
    last_error: str
    attempts: int
