"""``_ReflexionLoop`` — the actor/evaluator/reflection loop as a core node.

Replaces the hand-rolled ``for index in range(max_iterations): ... actor
.process(...); evaluator.process(...); reflector.process(...)`` that called
the constituent knots' ``process()`` directly instead of through the engine
(``Knot.__call__``), with an unrun ``Tapestry()`` opened only so the knots had
somewhere to register (ADR agents-speaks-core WS5b; PIR-856's
imperative-loop inventory).

Every iteration now wires ``ReflexionActor`` and ``ReflexionEvaluator`` as
real parent/child knots in one tapestry the engine actually runs.
``ReflexionReflector``'s LLM call runs only on a failed attempt: its
``answer`` input is ``Gate(input=actor, check=_ShouldReflectCheck(evaluation))``
(see that check's docstring), so a successful attempt never pays for it —
the same escalation-stops-here shape ``_AttemptTier`` uses.

Memory I/O (``retrieve`` the accumulated reflections before building the
iteration, ``store`` a new one after) is not an LLM/tool call, so it runs in
``astep``/``afold`` themselves, the same way the module docstring's own
example runs "a budget check against a remote meter" there.

Internal API. See PIR-856.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from pirn.core.knot_config import KnotConfig
from pirn.nodes.gate.gate import Gate
from pirn.tapestry import Tapestry

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.memory.stores.memory_store import MemoryStore
from pirn_agents.specializations.base.agent_loop_pipeline import AgentLoopPipeline
from pirn_agents.specializations.reflexion._evaluation_feedback import _EvaluationFeedback
from pirn_agents.specializations.reflexion._reflexion_state import _ReflexionState
from pirn_agents.specializations.reflexion._should_reflect_check import _ShouldReflectCheck
from pirn_agents.specializations.reflexion.reflexion_actor import ReflexionActor
from pirn_agents.specializations.reflexion.reflexion_attempt import ReflexionAttempt
from pirn_agents.specializations.reflexion.reflexion_evaluator import ReflexionEvaluator
from pirn_agents.specializations.reflexion.reflexion_reflector import ReflexionReflector

if TYPE_CHECKING:
    from pirn.core.run_result import RunResult


class _ReflexionLoop(AgentLoopPipeline[_ReflexionState]):
    """Drive the bounded actor/evaluator/reflection cycle."""

    #: Per-iteration knot ids (Rule: no module-level constants).
    _actor_id: ClassVar[str] = "actor"
    _evaluator_id: ClassVar[str] = "evaluator"
    _reflect_id: ClassVar[str] = "reflect"

    def __init__(
        self,
        *,
        task: str,
        llm: LLMProvider,
        memory: MemoryStore,
        max_iterations: int,
        memory_namespace: str,
        **kwargs: Any,
    ) -> None:
        self._task = task
        self._llm = llm
        self._memory = memory
        self._max_iterations = max_iterations
        self._memory_namespace = memory_namespace
        super().__init__(**kwargs)

    async def astep(self, state: _ReflexionState) -> tuple[Tapestry, _ReflexionState] | None:
        """Build the next iteration, or return None once accepted or exhausted.

        Reads back every reflection written by an earlier iteration (memory
        I/O, not an LLM/tool call) before building the actor/evaluator/
        reflector graph.

        Args:
            state: Accumulated state from the previous ``afold``.

        Returns:
            The iteration's tapestry paired with ``state``, or ``None`` once
            ``state.succeeded`` or ``state.index`` has reached the cap.
        """
        if state.succeeded or state.index >= self._max_iterations:
            return None

        reflections = await self._read_reflections(state.reflection_keys)
        iteration = Tapestry()
        with iteration:
            actor = ReflexionActor(
                task=self._task,
                llm=self._llm,
                reflections=reflections,
                _config=KnotConfig(id=self._actor_id),
            )
            evaluator = ReflexionEvaluator(
                task=self._task,
                answer=actor,
                llm=self._llm,
                _config=KnotConfig(id=self._evaluator_id),
            )
            should_reflect = _ShouldReflectCheck(
                evaluation=evaluator, _config=KnotConfig(id="should_reflect")
            )
            gated_answer = Gate(
                input=actor, check=should_reflect, _config=KnotConfig(id="gated_answer")
            )
            feedback = _EvaluationFeedback(evaluation=evaluator, _config=KnotConfig(id="feedback"))
            ReflexionReflector(
                task=self._task,
                answer=gated_answer,
                feedback=feedback,
                llm=self._llm,
                _config=KnotConfig(id=self._reflect_id),
            )
        return iteration, state

    async def afold(self, state: _ReflexionState, result: RunResult) -> _ReflexionState:
        """Record the attempt; write and key a new reflection on failure.

        Args:
            state: State as ``astep`` returned it.
            result: The iteration's run result.

        Returns:
            A new state with the attempt recorded, ``succeeded`` set on
            acceptance, or a new reflection key appended on failure.
        """
        answer = result.outputs[self._actor_id]
        evaluation = result.outputs[self._evaluator_id]
        index = state.index + 1
        if evaluation.success:
            attempts = (
                *state.attempts,
                ReflexionAttempt(answer=answer, success=True, feedback="", reflection=""),
            )
            return _ReflexionState(
                reflection_keys=state.reflection_keys,
                attempts=attempts,
                final_answer=answer,
                succeeded=True,
                index=index,
            )

        reflection = result.outputs[self._reflect_id]
        key = f"{self._memory_namespace}:{state.index}"
        await self._memory.store(key, {"text": reflection})
        attempts = (
            *state.attempts,
            ReflexionAttempt(
                answer=answer, success=False, feedback=evaluation.feedback, reflection=reflection
            ),
        )
        return _ReflexionState(
            reflection_keys=(*state.reflection_keys, key),
            attempts=attempts,
            final_answer=answer,
            succeeded=False,
            index=index,
        )

    def step_id(self, state: _ReflexionState, idx: int) -> str:
        """Name each iteration for run history."""
        return f"iteration_{idx}"

    async def _read_reflections(self, keys: tuple[str, ...]) -> tuple[str, ...]:
        """Read back every previously written reflection from the memory store."""
        texts: list[str] = []
        for key in keys:
            entry = await self._memory.retrieve(key)
            if entry is not None:
                text = entry.get("text")
                if isinstance(text, str):
                    texts.append(text)
        return tuple(texts)
