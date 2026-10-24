"""``EvaluatorOptimizerState`` — the value threaded through the refine loop.

Internal API.
"""

from __future__ import annotations

from dataclasses import dataclass

from pirn_agents.llm.llm_provider import LLMProvider


@dataclass(frozen=True)
class EvaluatorOptimizerState:
    """One iteration's worth of accumulated loop state.

    Frozen, and ``fold`` returns a *new* instance rather than mutating: PIR-754
    made ``fold`` receive the state ``step`` returned, and ``docs/guides/
    agentic-loops.md`` blesses returning a new state object. Mutating in place
    would work today but is the shape that hid the original defect.

    Attributes:
        task: The task every candidate answers.
        llm: The provider each generation and judgement call uses.
        threshold: Score at or above which the accept gate fires.
        max_iterations: Hard cap on iterations.
        reflection_gate: Whether the optional reflection gate runs.
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
