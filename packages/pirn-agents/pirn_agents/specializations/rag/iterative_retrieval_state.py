"""``IterativeRetrievalState`` — state threaded across retrieve-and-refine rounds."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.memory.stores.memory_store import MemoryStore


@dataclass
class IterativeRetrievalState(PirnOpaqueValue):
    """A retrieve-and-refine run's inputs plus the rounds accumulated so far.

    The loop reads the store, the provider, the round budget and ``top_k`` of a run from
    this value, not from instance attributes on the loop knot. Inputs held on the knot
    break two contracts: ``step``/``fold`` can then only be exercised through a
    constructor that re-supplies them, not called standalone with plain values
    (knot-design-rules.md Rules 2 and 4), and the state a run records in lineage omits
    what the run was actually driven by. It is also unsafe the moment such a loop is wired
    into a graph that outlives one invocation rather than rebuilt inside its pipeline's
    ``process()``, since the knot object is then shared by every run of that graph
    (PIR-873).

    Attributes:
        original_query: The user's question, which every refinement is judged
            against.
        memory: The store each round searches.
        llm: The provider deciding whether to refine the query.
        max_iterations: Round cap.
        top_k: Hits fetched per round.
        current_query: The query the next round searches for.
        merged: Every hit seen so far, keyed by identity.
        iteration: How many rounds have completed.
        done: Whether the loop was told to stop.
    """

    original_query: str
    memory: MemoryStore
    llm: LLMProvider
    max_iterations: int
    top_k: int
    current_query: str
    merged: dict[str, Mapping[str, Any]] = field(default_factory=dict[str, Mapping[str, Any]])
    iteration: int = 0
    done: bool = False

    def is_last_round(self) -> bool:
        """Whether the round about to run is the last the budget allows."""
        return self.iteration == self.max_iterations - 1

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "original_query": self.original_query,
            "memory": type(self.memory).__name__,
            "llm": type(self.llm).__name__,
            "max_iterations": self.max_iterations,
            "top_k": self.top_k,
            "current_query": self.current_query,
            "merged": sorted(self.merged),
            "iteration": self.iteration,
            "done": self.done,
        }
