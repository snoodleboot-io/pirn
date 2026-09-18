"""``AgenticRagState`` — state threaded across agentic-RAG rounds."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.tools.tool_factory import ToolFactory


@dataclass
class AgenticRagState(PirnOpaqueValue):
    """An agentic-RAG run's inputs plus the rounds accumulated so far.

    The loop reads the original query, the retrieval tool, the provider and the round
    budget of a run from this value, not from instance attributes on the loop knot.
    Inputs held on the knot break two contracts: ``step``/``fold`` can then only be
    exercised through a constructor that re-supplies them, not called standalone with
    plain values (knot-design-rules.md Rules 2 and 4), and the state a run records in
    lineage omits what the run was actually driven by. It is also unsafe the moment such
    a loop is wired into a graph that outlives one invocation rather than rebuilt inside
    its pipeline's ``process()``, since the knot object is then shared by every run of
    that graph (PIR-873).

    Attributes:
        query: The user's original question, which every follow-up decision is
            judged against.
        rag_tool: The retrieval tool each round calls.
        llm: The provider deciding whether to ask a follow-up.
        max_iterations: Hard upper bound on rounds.
        current_question: The question the next round retrieves for.
        answer: The most recent round's answer.
        iteration: How many rounds have completed.
        done: Whether the loop was told to stop.
    """

    query: str
    rag_tool: ToolFactory
    llm: LLMProvider
    max_iterations: int
    current_question: str
    answer: str = ""
    iteration: int = 0
    done: bool = False

    def is_last_round(self) -> bool:
        """Whether the round about to run is the last the budget allows."""
        return self.iteration == self.max_iterations - 1

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "rag_tool": self.rag_tool.name,
            "llm": type(self.llm).__name__,
            "max_iterations": self.max_iterations,
            "current_question": self.current_question,
            "answer": self.answer,
            "iteration": self.iteration,
            "done": self.done,
        }
