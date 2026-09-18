"""``ConstitutionalState`` — the value threaded through the revision loop.

Internal API. See ``constitutional_filter_loop.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.llm.llm_provider import LLMProvider


@dataclass(frozen=True)
class ConstitutionalState(PirnOpaqueValue):
    """One revision attempt's worth of accumulated constitutional-review state.

    The loop reads the provider, the evaluation system prompt and the revision cap of a
    run from this value, not from instance attributes on the loop knot. Inputs held on
    the knot break two contracts: ``step``/``fold`` can then only be exercised through a
    constructor that re-supplies them, not called standalone with plain values (knot-
    design-rules.md Rules 2 and 4), and the state a run records in lineage omits what
    the run was actually driven by. It is also unsafe the moment such a loop is wired
    into a graph that outlives one invocation rather than rebuilt inside its pipeline's
    ``process()``, since the knot object is then shared by every run of that graph
    (PIR-873).

    Frozen; ``fold`` returns a new instance rather than mutating, matching
    every other ``LoopSubTapestry`` state in this package.

    Attributes:
        principles_text: The bulleted principles list, rendered once and
            carried unchanged through every attempt.
        llm: The provider every evaluation attempt calls.
        evaluation_system: The system prompt every attempt sends.
        max_revisions: The attempt cap.
        current_content: The response text being evaluated -- the original
            response before any attempt, or the LLM's revised text.
        attempts: How many evaluation attempts have completed.
        compliant: Whether the most recent evaluation reported ``COMPLIANT``.
    """

    principles_text: str
    llm: LLMProvider
    evaluation_system: str
    max_revisions: int
    current_content: str
    attempts: int
    compliant: bool

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "principles_text": self.principles_text,
            "llm": type(self.llm).__name__,
            "evaluation_system": self.evaluation_system,
            "max_revisions": self.max_revisions,
            "current_content": self.current_content,
            "attempts": self.attempts,
            "compliant": self.compliant,
        }
