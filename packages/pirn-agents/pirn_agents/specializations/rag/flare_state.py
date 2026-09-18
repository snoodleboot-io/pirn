"""``FlareState`` — the value threaded through the FLARE sentence-generation loop.

Internal API. See ``flare_loop.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.memory.stores.memory_store import MemoryStore


@dataclass(frozen=True)
class FlareState(PirnOpaqueValue):
    """One round's worth of accumulated FLARE generation state.

    The loop reads the query, the store, the provider and all four bounds of a run from
    this value, not from instance attributes on the loop knot. Inputs held on the knot
    break two contracts: ``step``/``fold`` can then only be exercised through a
    constructor that re-supplies them, not called standalone with plain values
    (knot-design-rules.md Rules 2 and 4), and the state a run records in lineage omits
    what the run was actually driven by. It is also unsafe the moment such a loop is wired
    into a graph that outlives one invocation rather than rebuilt inside its pipeline's
    ``process()``, since the knot object is then shared by every run of that graph
    (PIR-873).

    Frozen; ``afold`` returns a new instance rather than mutating, matching
    every other ``LoopSubTapestry`` state in this package.

    Attributes:
        query: The question every round generates the next sentence of.
        memory: The store a low-confidence sentence retrieves against.
        llm: The provider every generation and regeneration calls.
        confidence_threshold: Below this, the round retrieves and regenerates.
        max_sentences: Round cap.
        max_retrieval_calls: Hard cap on retrieval calls across the run.
        top_k: Hits fetched per retrieval.
        parts: The assembled answer sentences so far, in order.
        retrieval_calls: How many retrieval calls have been spent so far.
        done: Whether the model signalled ``DONE``.
        index: How many rounds have completed (bounds the loop even when a
            round produces an empty sentence, matching the original
            ``for _step in range(max_sentences)``).
    """

    query: str
    memory: MemoryStore
    llm: LLMProvider
    confidence_threshold: float
    max_sentences: int
    max_retrieval_calls: int
    top_k: int
    parts: tuple[str, ...]
    retrieval_calls: int
    done: bool
    index: int

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "memory": type(self.memory).__name__,
            "llm": type(self.llm).__name__,
            "confidence_threshold": self.confidence_threshold,
            "max_sentences": self.max_sentences,
            "max_retrieval_calls": self.max_retrieval_calls,
            "top_k": self.top_k,
            "parts": list(self.parts),
            "retrieval_calls": self.retrieval_calls,
            "done": self.done,
            "index": self.index,
        }
