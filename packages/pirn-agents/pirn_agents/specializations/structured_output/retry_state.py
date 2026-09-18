"""``RetryState`` — the value threaded through the parse-retry loop.

Internal API. See ``retry_on_parse_failure_loop.py``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.llm.llm_provider import LLMProvider


@dataclass(frozen=True)
class RetryState(PirnOpaqueValue):
    """One attempt's worth of accumulated parse-retry state.

    The loop reads every per-run input from this value, not from instance attributes on
    the loop knot. Inputs held on the knot break two contracts: ``step``/``fold`` can
    then only be exercised through a constructor that re-supplies them, not called
    standalone with plain values (knot-design-rules.md Rules 2 and 4), and the state a
    run records in lineage omits what the run was actually driven by. It is also unsafe
    the moment such a loop is wired into a graph that outlives one invocation rather
    than rebuilt inside its pipeline's ``process()``, since the knot object is then
    shared by every run of that graph (PIR-873).

    Frozen; ``fold`` returns a new instance rather than mutating, matching
    every other ``LoopSubTapestry`` state in this package.

    Attributes:
        original_prompt: The prompt as the caller supplied it, prefixed onto
            every retry alongside the previous error.
        llm: The provider every attempt calls.
        parser: The parse the reply must satisfy; a raise is the retry trigger.
        max_retries: The attempt cap.
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

    original_prompt: str
    llm: LLMProvider
    parser: Callable[[str], Any]
    max_retries: int
    prompt: str
    parsed_value: Any
    succeeded: bool
    last_error: str
    attempts: int

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "original_prompt": self.original_prompt,
            "llm": type(self.llm).__name__,
            "parser": getattr(self.parser, "__qualname__", repr(self.parser)),
            "max_retries": self.max_retries,
            "prompt": self.prompt,
            "succeeded": self.succeeded,
            "last_error": self.last_error,
            "attempts": self.attempts,
        }
