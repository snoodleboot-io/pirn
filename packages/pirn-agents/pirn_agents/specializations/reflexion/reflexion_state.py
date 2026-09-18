"""``ReflexionState`` — the value threaded through the actor/evaluator/reflection loop.

Internal API. See ``reflexion_loop.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.memory.stores.memory_store import MemoryStore
from pirn_agents.specializations.reflexion.reflexion_attempt import ReflexionAttempt


@dataclass(frozen=True)
class ReflexionState(PirnOpaqueValue):
    """One iteration's worth of accumulated Reflexion state.

    The loop reads the task, the provider, the memory store, the iteration cap and the
    memory namespace of a run from this value, not from instance attributes on the loop
    knot. Inputs held on the knot break two contracts: ``step``/``fold`` can then only
    be exercised through a constructor that re-supplies them, not called standalone with
    plain values (knot-design-rules.md Rules 2 and 4), and the state a run records in
    lineage omits what the run was actually driven by. It is also unsafe the moment such
    a loop is wired into a graph that outlives one invocation rather than rebuilt inside
    its pipeline's ``process()``, since the knot object is then shared by every run of
    that graph (PIR-873).

    Frozen; ``afold`` returns a new instance rather than mutating, matching
    every other ``LoopSubTapestry`` state in this package.

    Attributes:
        task: The task every attempt answers.
        llm: The provider the actor, evaluator and reflector call.
        memory: The store reflections are written to and read back from.
        max_iterations: The attempt cap.
        memory_namespace: Key prefix for this run's reflections.
        reflection_keys: Memory-store keys written by prior failed attempts,
            in order — read back at the start of the next iteration.
        attempts: The per-attempt records completed so far, in order.
        final_answer: The most recent actor answer.
        succeeded: Whether the evaluator accepted an attempt.
        index: How many iterations have completed.
    """

    task: str
    llm: LLMProvider
    memory: MemoryStore
    max_iterations: int
    memory_namespace: str
    reflection_keys: tuple[str, ...]
    attempts: tuple[ReflexionAttempt, ...]
    final_answer: str
    succeeded: bool
    index: int

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "task": self.task,
            "llm": type(self.llm).__name__,
            "memory": type(self.memory).__name__,
            "max_iterations": self.max_iterations,
            "memory_namespace": self.memory_namespace,
            "reflection_keys": list(self.reflection_keys),
            "attempt_count": len(self.attempts),
            "final_answer": self.final_answer,
            "succeeded": self.succeeded,
            "index": self.index,
        }
