"""``SelfAskState`` — the value threaded through the sub-answer loop.

Internal API. See ``self_ask_loop.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.llm.llm_provider import LLMProvider


@dataclass(frozen=True)
class SelfAskState(PirnOpaqueValue):
    """One round's worth of accumulated Self-Ask sub-answer state.

    The loop reads the provider and the sub-answer system prompt of a run from this
    value, not from instance attributes on the loop knot. Inputs held on the knot break
    two contracts: ``step``/``fold`` can then only be exercised through a constructor
    that re-supplies them, not called standalone with plain values (knot-design-rules.md
    Rules 2 and 4), and the state a run records in lineage omits what the run was
    actually driven by. It is also unsafe the moment such a loop is wired into a graph
    that outlives one invocation rather than rebuilt inside its pipeline's
    ``process()``, since the knot object is then shared by every run of that graph
    (PIR-873).

    Frozen; ``fold`` returns a new instance rather than mutating, matching
    every other ``LoopSubTapestry`` state in this package.

    Attributes:
        subquestions: The full, fixed sub-question list decided before the
            loop started (decomposition already ran; this loop only answers
            each in turn).
        llm: The provider every round calls.
        subanswer_system: The system prompt every round sends.
        index: How many sub-questions have been answered so far — also the
            0-based index of the next sub-question to answer.
        subanswers: The answers collected so far, in sub-question order.
    """

    subquestions: tuple[str, ...]
    llm: LLMProvider
    subanswer_system: str
    index: int
    subanswers: tuple[str, ...]

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "subquestions": list(self.subquestions),
            "llm": type(self.llm).__name__,
            "subanswer_system": self.subanswer_system,
            "index": self.index,
            "subanswers": list(self.subanswers),
        }
