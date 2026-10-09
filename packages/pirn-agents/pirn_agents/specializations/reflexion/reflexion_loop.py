"""``ReflexionLoop`` — the actor/evaluator/reflection loop as a core node.

Replaces the hand-rolled ``for index in range(max_iterations): ... actor
.process(...); evaluator.process(...); reflector.process(...)`` that called
the constituent knots' ``process()`` directly instead of through the engine
(``Knot.__call__``), with an unrun ``Tapestry()`` opened only so the knots had
somewhere to register (ADR agents-speaks-core WS5b; PIR-856's
imperative-loop inventory).

Every iteration now wires ``ReflexionActor`` and ``ReflexionEvaluator`` as
real parent/child knots in one tapestry the engine actually runs.
``ReflexionReflector``'s LLM call runs only on a failed attempt: its
``answer`` input is ``Gate(input=actor, check=ShouldReflectCheck(evaluation))``
(see that check's docstring), so a successful attempt never pays for it —
the same escalation-stops-here shape ``AttemptTier`` uses.

Memory I/O.  Reading the accumulated reflections back is N store calls, so each
is a :class:`~pirn_agents.specializations.reflexion.recalled_reflection.RecalledReflection`
*inside* the iteration's tapestry, feeding the actor through an
:class:`~pirn.nodes.aggregator.Aggregator` — one lineage row, ``Result``, retry
and timeout per read, instead of a ``for`` loop in ``astep`` the run cannot see
(Rule 11; PIR-874).  Writing the new reflection stays in ``afold``: it is one
call, and it happens after the iteration has finished.

Internal API. See PIR-856.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.nodes.aggregator import Aggregator
from pirn.nodes.gate.gate import Gate
from pirn.tapestry import Tapestry

from pirn_agents.memory.stores.memory_store import MemoryStore
from pirn_agents.specializations.base.agent_loop_pipeline import AgentLoopPipeline
from pirn_agents.specializations.reflexion.evaluation_feedback import EvaluationFeedback
from pirn_agents.specializations.reflexion.recalled_reflection import RecalledReflection
from pirn_agents.specializations.reflexion.reflexion_actor import ReflexionActor
from pirn_agents.specializations.reflexion.reflexion_attempt import ReflexionAttempt
from pirn_agents.specializations.reflexion.reflexion_evaluator import ReflexionEvaluator
from pirn_agents.specializations.reflexion.reflexion_reflector import ReflexionReflector
from pirn_agents.specializations.reflexion.reflexion_state import ReflexionState
from pirn_agents.specializations.reflexion.should_reflect_check import ShouldReflectCheck

if TYPE_CHECKING:
    from pirn.core.run_result import RunResult


class ReflexionLoop(AgentLoopPipeline[ReflexionState]):
    """Drive the bounded actor/evaluator/reflection cycle."""

    #: Per-iteration knot ids (Rule: no module-level constants).
    _actor_id: ClassVar[str] = "actor"
    _evaluator_id: ClassVar[str] = "evaluator"
    _reflect_id: ClassVar[str] = "reflect"
    _reflection_prefix: ClassVar[str] = "reflection_"

    async def astep(self, state: ReflexionState) -> tuple[Tapestry, ReflexionState] | None:
        """Build the next iteration, or return None once accepted or exhausted.

        Every reflection an earlier iteration wrote is read by its own knot
        inside the iteration's tapestry; the actor's ``reflections`` input is
        the aggregator over them. The first iteration has no keys, and
        ``Aggregator`` needs at least one parent, so it is handed the empty
        tuple directly.

        Args:
            state: Accumulated state from the previous ``afold``.

        Returns:
            The iteration's tapestry paired with ``state``, or ``None`` once
            ``state.succeeded`` or ``state.index`` has reached the cap.
        """
        if state.succeeded or state.index >= state.max_iterations:
            return None

        iteration = Tapestry()
        with iteration:
            reflections: Knot | tuple[str, ...] = ()
            if state.reflection_keys:
                memory_node = Parameter(
                    "memory",
                    MemoryStore,
                    default=state.memory,
                    _config=KnotConfig(id="memory"),
                )
                per_key: dict[str, Knot] = {
                    f"{self._reflection_prefix}{index}": RecalledReflection(
                        memory=memory_node,
                        key=key,
                        _config=KnotConfig(id=f"{self._reflection_prefix}{index}"),
                    )
                    for index, key in enumerate(state.reflection_keys)
                }
                reflections = Aggregator(
                    combine=ReflexionLoop._in_key_order,
                    _config=KnotConfig(id="reflections"),
                    **per_key,
                )
            actor = ReflexionActor(
                task=state.task,
                llm=state.llm,
                reflections=reflections,
                _config=KnotConfig(id=self._actor_id),
            )
            evaluator = ReflexionEvaluator(
                task=state.task,
                answer=actor,
                llm=state.llm,
                _config=KnotConfig(id=self._evaluator_id),
            )
            should_reflect = ShouldReflectCheck(
                evaluation=evaluator, _config=KnotConfig(id="should_reflect")
            )
            gated_answer = Gate(
                input=actor, check=should_reflect, _config=KnotConfig(id="gated_answer")
            )
            feedback = EvaluationFeedback(evaluation=evaluator, _config=KnotConfig(id="feedback"))
            ReflexionReflector(
                task=state.task,
                answer=gated_answer,
                feedback=feedback,
                llm=state.llm,
                _config=KnotConfig(id=self._reflect_id),
            )
        return iteration, state

    async def afold(self, state: ReflexionState, result: RunResult) -> ReflexionState:
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
            return ReflexionState(
                task=state.task,
                llm=state.llm,
                memory=state.memory,
                max_iterations=state.max_iterations,
                memory_namespace=state.memory_namespace,
                reflection_keys=state.reflection_keys,
                attempts=attempts,
                final_answer=answer,
                succeeded=True,
                index=index,
            )

        reflection = result.outputs[self._reflect_id]
        key = f"{state.memory_namespace}:{state.index}"
        await state.memory.store(key, {"text": reflection})
        attempts = (
            *state.attempts,
            ReflexionAttempt(
                answer=answer, success=False, feedback=evaluation.feedback, reflection=reflection
            ),
        )
        return ReflexionState(
            task=state.task,
            llm=state.llm,
            memory=state.memory,
            max_iterations=state.max_iterations,
            memory_namespace=state.memory_namespace,
            reflection_keys=(*state.reflection_keys, key),
            attempts=attempts,
            final_answer=answer,
            succeeded=False,
            index=index,
        )

    def step_id(self, state: ReflexionState, idx: int) -> str:
        """Name each iteration for run history."""
        return f"iteration_{idx}"

    @staticmethod
    def _in_key_order(**reflections: str | None) -> tuple[str, ...]:
        """Put the per-key reads back in the order the keys were written.

        Keys are ``reflection_<index>``; sorting on the index rather than on the
        mapping's order keeps the prompt the actor sees independent of how the
        engine happened to schedule the reads. A key with nothing behind it
        contributes nothing, as the loop it replaced did.
        """
        ordered = sorted(
            reflections.items(), key=lambda item: int(item[0].removeprefix("reflection_"))
        )
        return tuple(text for _key, text in ordered if text is not None)
