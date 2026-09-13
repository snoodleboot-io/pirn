"""``ReflexionPipeline`` — bounded actor/evaluator/reflection loop with F4 memory.

A :class:`SubTapestry` that runs, up to ``max_iterations`` times:

1. :class:`ReflexionActor` drafts an answer, conditioned on the verbal
   reflections read back from the :class:`MemoryStore`.
2. :class:`ReflexionEvaluator` judges the answer.
3. On success, the loop returns; otherwise :class:`ReflexionReflector` distils
   a lesson which is **written to** the memory store and **read back** on the
   next iteration — the persistent-memory characteristic of Reflexion.

The loop is strictly bounded by ``max_iterations`` and returns a typed
:class:`ReflexionResult` on either success or exhaustion. Driven by
:class:`~pirn_agents.specializations.reflexion._reflexion_loop._ReflexionLoop`
(a :class:`~pirn.nodes.loop_sub_tapestry.LoopSubTapestry`): every iteration
wires the actor and evaluator as real parent/child knots the engine actually
runs, instead of calling their ``process()`` methods directly inside a
hand-rolled Python ``for`` loop (ADR agents-speaks-core WS5b).

References:
    - Shinn et al. (2023) "Reflexion" https://arxiv.org/abs/2303.11366
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.memory.stores.memory_store import MemoryStore
from pirn_agents.specializations.base.agent_pipeline import AgentPipeline
from pirn_agents.specializations.reflexion._reflexion_loop import _ReflexionLoop
from pirn_agents.specializations.reflexion._reflexion_result_extractor import (
    _ReflexionResultExtractor,
)
from pirn_agents.specializations.reflexion._reflexion_state import _ReflexionState


class ReflexionPipeline(AgentPipeline):
    """Memory-backed actor/evaluator/reflection retry loop."""

    def __init__(
        self,
        *,
        task: Knot | str,
        llm: Knot | LLMProvider,
        memory: Knot | MemoryStore,
        max_iterations: Knot | int = 3,
        memory_namespace: Knot | str = "reflexion",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            task=task,
            llm=llm,
            memory=memory,
            max_iterations=max_iterations,
            memory_namespace=memory_namespace,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        task: str,
        llm: LLMProvider,
        memory: MemoryStore,
        max_iterations: int = 3,
        memory_namespace: str = "reflexion",
        **_: Any,
    ) -> Knot:
        """Run the bounded Reflexion loop and surface a :class:`ReflexionResult`.

        Args:
            task: The task to solve.
            llm: Provider shared by the actor, evaluator, and reflector.
            memory: Store reflections are written to and read back from.
            max_iterations: Hard cap on actor attempts.
            memory_namespace: Key prefix for this run's reflections.

        Returns:
            The sink knot whose output is the :class:`ReflexionResult`.

        Raises:
            ValueError: If ``max_iterations`` is not a positive int.
        """
        if not isinstance(max_iterations, int) or max_iterations <= 0:
            raise ValueError(
                f"ReflexionPipeline: max_iterations must be a positive int, got {max_iterations!r}"
            )

        initial = Parameter(
            "reflexion_state",
            _ReflexionState,
            default=_ReflexionState(
                reflection_keys=(), attempts=(), final_answer="", succeeded=False, index=0
            ),
        )
        loop = _ReflexionLoop(
            task=task,
            llm=llm,
            memory=memory,
            max_iterations=max_iterations,
            memory_namespace=memory_namespace,
            state=initial,
            _config=KnotConfig(id="reflexion_loop"),
        )
        return _ReflexionResultExtractor(state=loop, _config=KnotConfig(id="reflexion_result"))
