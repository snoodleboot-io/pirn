"""``EvaluatorOptimizerState`` — the value threaded through the refine loop.

Internal API.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.llm.llm_provider import LLMProvider


@dataclass(frozen=True)
class EvaluatorOptimizerState(PirnOpaqueValue):
    """One iteration's worth of accumulated loop state.

    The loop reads the task, the provider, the accept threshold, the iteration cap and
    the reflection-gate flag of a run from this value, not from instance attributes on
    the loop knot. Inputs held on the knot break two contracts: ``step``/``fold`` can
    then only be exercised through a constructor that re-supplies them, not called
    standalone with plain values (knot-design-rules.md Rules 2 and 4), and the state a
    run records in lineage omits what the run was actually driven by. It is also unsafe
    the moment such a loop is wired into a graph that outlives one invocation rather
    than rebuilt inside its pipeline's ``process()``, since the knot object is then
    shared by every run of that graph (PIR-873).

    Frozen, and ``fold`` returns a *new* instance rather than mutating: PIR-754
    made ``fold`` receive the state ``step`` returned, and ``docs/guides/
    agentic-loops.md`` blesses returning a new state object. Mutating in place
    would work today but is the shape that hid the original defect.

    Attributes:
        task: The task every candidate answers.
        llm: The provider the generator, judge and reflection check call.
        threshold: The judge score at or above which a candidate is accepted.
        max_iterations: The iteration cap.
        reflection_gate: Whether a rejected candidate is passed to a
            reflection check that may stop the loop early.
        feedback: The judge's last feedback, fed to the next generation. Empty
            on round one.
        best_answer: Best candidate seen so far.
        best_score: Score of ``best_answer``.
        accepted: Whether the accept gate has fired.
        iterations: How many iterations have completed.
        stop: Set when the optional reflection gate asked to stop early.
    """

    task: str
    llm: LLMProvider
    threshold: float
    max_iterations: int
    reflection_gate: bool
    feedback: str = ""
    best_answer: str = ""
    best_score: float = 0.0
    accepted: bool = False
    iterations: int = 0
    stop: bool = False

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "task": self.task,
            "llm": type(self.llm).__name__,
            "threshold": self.threshold,
            "max_iterations": self.max_iterations,
            "reflection_gate": self.reflection_gate,
            "feedback": self.feedback,
            "best_answer": self.best_answer,
            "best_score": self.best_score,
            "accepted": self.accepted,
            "iterations": self.iterations,
            "stop": self.stop,
        }
