"""``JsonExtractorState`` — the value threaded through the extraction-retry loop.

Internal API. See ``json_extractor_loop.py``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.llm.llm_provider import LLMProvider


@dataclass(frozen=True)
class JsonExtractorState(PirnOpaqueValue):
    """One attempt's worth of accumulated JSON-extraction state.

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
        prompt: The extraction prompt every attempt sends.
        llm: The provider every attempt calls.
        schema: The field names an attempt must produce.
        max_retries: The attempt cap.
        prior_error: The error to feed back into the next attempt's system
            prompt for self-correction, or the empty string before any
            attempt.
        result: The successfully parsed mapping, or ``None`` before success.
        last_error: The most recent attempt's error message, or the initial
            sentinel when no attempt has run yet.
        attempts: How many attempts have completed.
    """

    prompt: str
    llm: LLMProvider
    schema: Mapping[str, Any]
    max_retries: int
    prior_error: str
    result: Mapping[str, Any] | None
    last_error: str
    attempts: int

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "prompt": self.prompt,
            "llm": type(self.llm).__name__,
            "schema": sorted(self.schema),
            "max_retries": self.max_retries,
            "prior_error": self.prior_error,
            "parsed": self.result is not None,
            "last_error": self.last_error,
            "attempts": self.attempts,
        }
