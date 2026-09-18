"""``RoundRobinState`` — the value threaded through the reviewer loop.

Internal API. See ``round_robin_loop.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue
from pirn.nodes.sub_tapestry import SubTapestry

from pirn_agents.types.messaging.agent_response import AgentResponse


@dataclass(frozen=True)
class RoundRobinState(PirnOpaqueValue):
    """One iteration's worth of accumulated round-robin review state.

    The loop reads the reviewer sequence of a run from this value, not from instance
    attributes on the loop knot. Inputs held on the knot break two contracts:
    ``step``/``fold`` can then only be exercised through a constructor that re-supplies
    them, not called standalone with plain values (knot-design-rules.md Rules 2 and 4),
    and the state a run records in lineage omits what the run was actually driven by. It
    is also unsafe the moment such a loop is wired into a graph that outlives one
    invocation rather than rebuilt inside its pipeline's ``process()``, since the knot
    object is then shared by every run of that graph (PIR-873).

    Frozen; ``fold`` returns a new instance rather than mutating, matching
    every other ``LoopSubTapestry`` state in this package.

    Attributes:
        reviewers: The reviewers, run front to back, one per iteration.
        response: The response as revised by every reviewer up to and
            including the last completed iteration.
        index: How many reviewers have already run (0-based cursor into
            ``reviewers``).
    """

    reviewers: tuple[SubTapestry, ...]
    response: AgentResponse
    index: int

    def next_reviewer(self) -> SubTapestry | None:
        """The reviewer the next iteration runs, or ``None`` once all have run."""
        if self.index >= len(self.reviewers):
            return None
        return self.reviewers[self.index]

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "reviewers": [reviewer.knot_id for reviewer in self.reviewers],
            "response": self.response.data,
            "index": self.index,
        }
