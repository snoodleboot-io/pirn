"""``ReflexionPipeline`` — bounded actor/evaluator/reflection loop with F4 memory.

A :class:`SubTapestry` that runs, up to ``max_iterations`` times:

1. :class:`ReflexionActor` drafts an answer, conditioned on the verbal
   reflections read back from the :class:`MemoryStore`.
2. :class:`ReflexionEvaluator` judges the answer.
3. On success, the loop returns; otherwise :class:`ReflexionReflector` distils
   a lesson which is **written to** the memory store and **read back** on the
   next iteration — the persistent-memory characteristic of Reflexion.

The loop is strictly bounded by ``max_iterations`` and returns a typed
:class:`ReflexionResult` on either success or exhaustion. Orchestration happens
in ``process`` (the constituent knots' ``process`` methods are invoked directly),
and the final result is surfaced through a small terminal :class:`Source`, the
same shape :class:`OrchestratorAgent` uses.

References:
    - Shinn et al. (2023) "Reflexion" https://arxiv.org/abs/2303.11366
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.providers.llm_provider import LLMProvider
from pirn.nodes.source import Source
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry

from pirn_agents.memory_store import MemoryStore
from pirn_agents.specializations.reflexion.reflexion_actor import ReflexionActor
from pirn_agents.specializations.reflexion.reflexion_attempt import ReflexionAttempt
from pirn_agents.specializations.reflexion.reflexion_evaluator import ReflexionEvaluator
from pirn_agents.specializations.reflexion.reflexion_reflector import ReflexionReflector
from pirn_agents.specializations.reflexion.reflexion_result import ReflexionResult


class ReflexionPipeline(SubTapestry):
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
    ) -> Any:
        """Run the bounded Reflexion loop and surface a :class:`ReflexionResult`.

        Args:
            task: The task to solve.
            llm: Provider shared by the actor, evaluator, and reflector.
            memory: Store reflections are written to and read back from.
            max_iterations: Hard cap on actor attempts.
            memory_namespace: Key prefix for this run's reflections.

        Returns:
            A terminal :class:`Source` whose output is the
            :class:`ReflexionResult`.

        Raises:
            TypeError: If ``llm``/``memory``/``task`` have the wrong type.
            ValueError: If ``max_iterations`` is not a positive int.
        """
        if not isinstance(llm, LLMProvider):
            raise TypeError(
                f"ReflexionPipeline: llm must be an LLMProvider, got {type(llm).__name__}"
            )
        if not isinstance(memory, MemoryStore):
            raise TypeError(
                f"ReflexionPipeline: memory must be a MemoryStore, got {type(memory).__name__}"
            )
        if not isinstance(task, str):
            raise TypeError(f"ReflexionPipeline: task must be a string, got {type(task).__name__}")
        if not isinstance(max_iterations, int) or max_iterations <= 0:
            raise ValueError(
                f"ReflexionPipeline: max_iterations must be a positive int, got {max_iterations!r}"
            )

        with Tapestry():
            actor = ReflexionActor(task=task, llm=llm, _config=KnotConfig(id="reflexion_actor"))
            evaluator = ReflexionEvaluator(
                task=task, answer="", llm=llm, _config=KnotConfig(id="reflexion_eval")
            )
            reflector = ReflexionReflector(
                task=task,
                answer="",
                feedback="",
                llm=llm,
                _config=KnotConfig(id="reflexion_reflect"),
            )

        attempts: list[ReflexionAttempt] = []
        reflection_keys: list[str] = []
        final_answer = ""
        succeeded = False
        iterations = 0

        for index in range(max_iterations):
            iterations = index + 1
            reflections = await self._read_reflections(memory, reflection_keys)
            answer = await actor.process(task=task, llm=llm, reflections=reflections)
            evaluation = await evaluator.process(task=task, answer=answer, llm=llm)
            final_answer = answer
            if evaluation.success:
                attempts.append(
                    ReflexionAttempt(answer=answer, success=True, feedback="", reflection="")
                )
                succeeded = True
                break
            reflection = await reflector.process(
                task=task, answer=answer, feedback=evaluation.feedback, llm=llm
            )
            key = f"{memory_namespace}:{index}"
            await memory.store(key, {"text": reflection})
            reflection_keys.append(key)
            attempts.append(
                ReflexionAttempt(
                    answer=answer,
                    success=False,
                    feedback=evaluation.feedback,
                    reflection=reflection,
                )
            )

        result = ReflexionResult(
            answer=final_answer,
            succeeded=succeeded,
            iterations=iterations,
            attempts=tuple(attempts),
        )
        _result = result

        class _ReflexionResultSource(Source):
            async def process(self, **_: Any) -> ReflexionResult:
                return _result

        return _ReflexionResultSource(_config=KnotConfig(id="reflexion_result"))

    @staticmethod
    async def _read_reflections(memory: MemoryStore, keys: list[str]) -> tuple[str, ...]:
        """Read back every previously written reflection from the memory store."""
        texts: list[str] = []
        for key in keys:
            entry = await memory.retrieve(key)
            if entry is not None:
                text = entry.get("text")
                if isinstance(text, str):
                    texts.append(text)
        return tuple(texts)
