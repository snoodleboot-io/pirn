"""``FallbackChainState`` — state threaded across fallback candidates."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.specializations.routing.route_candidate import RouteCandidate
from pirn_agents.tools.tool_result import ToolResult


@dataclass
class FallbackChainState(PirnOpaqueValue):
    """A fallback chain's inputs plus the attempts accumulated so far.

    ``FallbackLoop`` reads the ordered candidates, the call arguments and the
    confidences of a run from this value, not from instance attributes on the loop knot.
    Inputs held on the knot break two contracts: ``step``/``fold`` can then only be
    exercised through a constructor that re-supplies them, not called standalone with
    plain values (knot-design-rules.md Rules 2 and 4), and the state a run records in
    lineage omits what the run was actually driven by. It is also unsafe the moment such
    a loop is wired into a graph that outlives one invocation rather than rebuilt inside
    its pipeline's ``process()``, since the knot object is then shared by every run of
    that graph (PIR-873).

    Attributes:
        ordered: The candidates in confidence-descending order, tried front to
            back.
        arguments: The arguments every candidate's tool call is made with.
        confidences: Per-candidate confidence, compared against each
            candidate's ``min_confidence`` to decide whether to attempt it.
        attempted: The names of the candidates actually called, in order.
        skipped: The names of the candidates skipped for low confidence.
        succeeded_result: The winning call's result, once one succeeds.
        chosen: The candidate that produced ``succeeded_result``.
        locked: Whether the chain has stopped.
    """

    ordered: tuple[RouteCandidate, ...]
    arguments: Mapping[str, Any]
    confidences: Mapping[str, float]
    attempted: tuple[str, ...] = ()
    skipped: tuple[str, ...] = ()
    succeeded_result: ToolResult | None = None
    chosen: str | None = None
    locked: bool = False

    def next_candidate(self) -> RouteCandidate | None:
        """The candidate the next attempt runs, or ``None`` once locked or exhausted."""
        index = len(self.attempted) + len(self.skipped)
        if self.locked or index >= len(self.ordered):
            return None
        return self.ordered[index]

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "ordered": [candidate.name for candidate in self.ordered],
            "arguments": sorted(self.arguments),
            "confidences": dict(sorted(self.confidences.items())),
            "attempted": list(self.attempted),
            "skipped": list(self.skipped),
            "chosen": self.chosen,
            "locked": self.locked,
        }
