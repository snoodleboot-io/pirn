"""``_ReflexionState`` — the value threaded through the actor/evaluator/reflection loop.

Internal API. See ``_reflexion_loop.py``.
"""

from __future__ import annotations

from dataclasses import dataclass

from pirn_agents.specializations.reflexion.reflexion_attempt import ReflexionAttempt


@dataclass(frozen=True)
class _ReflexionState:
    """One iteration's worth of accumulated Reflexion state.

    Frozen; ``afold`` returns a new instance rather than mutating, matching
    every other ``LoopSubTapestry`` state in this package.

    Attributes:
        reflection_keys: Memory-store keys written by prior failed attempts,
            in order — read back at the start of the next iteration.
        attempts: The per-attempt records completed so far, in order.
        final_answer: The most recent actor answer.
        succeeded: Whether the evaluator accepted an attempt.
        index: How many iterations have completed.
    """

    reflection_keys: tuple[str, ...]
    attempts: tuple[ReflexionAttempt, ...]
    final_answer: str
    succeeded: bool
    index: int
