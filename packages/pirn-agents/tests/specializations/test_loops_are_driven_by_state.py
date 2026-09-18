"""Behaviour test: every specialization loop is driven entirely by its state value.

Sixteen ``AgentLoopPipeline`` subclasses took their per-run inputs through a
constructor and parked them on ``self._x`` (``self._llm``, ``self._task``,
``self._max_iterations``, …). ``LoopSubTapestry`` declares exactly one input —
``state`` — so those constructor keywords were invisible to the framework: the
loop could not be built from its declared input alone, ``step``/``fold`` could
not be called standalone with plain values (knot-design-rules.md Rules 2 and 4),
and the state a run recorded in lineage omitted what the run was driven by.

This test builds each loop with ``state=`` and ``_config=`` only — nothing else —
and drives one ``step`` off the state. On the old code every one of these raises
``TypeError`` for the missing constructor keywords. The loops that terminate
immediately for their seeded state prove the same thing by returning ``None``
without ever touching an instance attribute.
"""

from __future__ import annotations

import unittest
from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.llm.stream_delta import StreamDelta
from pirn_agents.memory.stores.memory_store import MemoryStore
from pirn_agents.performance.spend_cap_policy import SpendCapPolicy
from pirn_agents.specializations.evaluator_optimizer.evaluator_optimizer_loop import (
    EvaluatorOptimizerLoop,
)
from pirn_agents.specializations.evaluator_optimizer.evaluator_optimizer_state import (
    EvaluatorOptimizerState,
)
from pirn_agents.specializations.plan_and_execute.plan_step_loop import PlanStepLoop
from pirn_agents.specializations.plan_and_execute.plan_step_state import PlanStepState
from pirn_agents.specializations.prompt_chaining.prompt_chain_loop import PromptChainLoop
from pirn_agents.specializations.prompt_chaining.prompt_chain_state import PromptChainState
from pirn_agents.specializations.rag.agentic_rag_loop import AgenticRagLoop
from pirn_agents.specializations.rag.agentic_rag_state import AgenticRagState
from pirn_agents.specializations.rag.flare_loop import FlareLoop
from pirn_agents.specializations.rag.flare_state import FlareState
from pirn_agents.specializations.rag.iterative_retrieval_loop import IterativeRetrievalLoop
from pirn_agents.specializations.rag.iterative_retrieval_state import IterativeRetrievalState
from pirn_agents.specializations.reflection.constitutional_filter_loop import (
    ConstitutionalFilterLoop,
)
from pirn_agents.specializations.reflection.constitutional_state import ConstitutionalState
from pirn_agents.specializations.reflexion.reflexion_loop import ReflexionLoop
from pirn_agents.specializations.reflexion.reflexion_state import ReflexionState
from pirn_agents.specializations.routing.cascade_chain_state import CascadeChainState
from pirn_agents.specializations.routing.cascade_loop import CascadeLoop
from pirn_agents.specializations.routing.fallback_chain_state import FallbackChainState
from pirn_agents.specializations.routing.fallback_loop import FallbackLoop
from pirn_agents.specializations.self_ask.self_ask_loop import SelfAskLoop
from pirn_agents.specializations.self_ask.self_ask_state import SelfAskState
from pirn_agents.specializations.structured_output.json_extractor_loop import JsonExtractorLoop
from pirn_agents.specializations.structured_output.json_extractor_state import JsonExtractorState
from pirn_agents.specializations.structured_output.pydantic_validator_loop import (
    PydanticValidatorLoop,
)
from pirn_agents.specializations.structured_output.pydantic_validator_state import (
    PydanticValidatorState,
)
from pirn_agents.specializations.structured_output.retry_on_parse_failure_loop import (
    RetryOnParseFailureLoop,
)
from pirn_agents.specializations.structured_output.retry_state import RetryState
from pirn_agents.specializations.structured_output.yaml_extractor_loop import YamlExtractorLoop
from pirn_agents.specializations.structured_output.yaml_extractor_state import YamlExtractorState
from pirn_agents.testing.stub_tool import StubTool
from pirn_agents.types.messaging.agent_response import AgentResponse


class _Llm(LLMProvider):
    """Minimal provider; no call is made by ``step`` alone."""

    async def chat(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> Mapping[str, Any]:
        return {"role": "assistant", "content": "unused"}

    def stream_chat(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> AsyncIterator[StreamDelta]:
        async def _aiter() -> AsyncIterator[StreamDelta]:
            yield StreamDelta(content="unused")

        return _aiter()

    async def close(self) -> None:
        return None


class _Store(MemoryStore):
    """Minimal store; no read or write is made by ``step`` alone."""

    async def store(self, key: str, value: Mapping[str, Any]) -> None:
        return None

    async def retrieve(self, key: str) -> Mapping[str, Any] | None:
        return None

    async def search(self, query: str, *, top_k: int = 10) -> Sequence[Mapping[str, Any]]:
        return []

    async def forget(self, key: str) -> None:
        return None

    async def close(self) -> None:
        return None


class TestLoopsAreDrivenByState(unittest.IsolatedAsyncioTestCase):
    """Each loop builds an iteration from ``state`` with no constructor inputs."""

    @staticmethod
    def _built(loop_class: Any, state: Any) -> Any:
        with Tapestry():
            return loop_class(state=state, _config=KnotConfig(id="loop"))

    async def _assert_steps(self, loop_class: Any, state: Any) -> None:
        loop = self._built(loop_class, state)
        outcome = await loop.astep(state)
        assert outcome is not None, f"{loop_class.__name__} planned no iteration"
        tapestry, returned = outcome
        assert returned is state
        assert tapestry.all_knots(), f"{loop_class.__name__} built an empty iteration"

    async def test_plan_step_loop(self) -> None:
        await self._assert_steps(PlanStepLoop, PlanStepState(steps=("do it",), llm=_Llm()))

    async def test_prompt_chain_loop(self) -> None:
        await self._assert_steps(
            PromptChainLoop,
            PromptChainState(steps=("a",), llm=_Llm(), index=0, current="seed", outputs=()),
        )

    async def test_self_ask_loop(self) -> None:
        await self._assert_steps(
            SelfAskLoop,
            SelfAskState(
                subquestions=("q?",),
                llm=_Llm(),
                subanswer_system="sys",
                index=0,
                subanswers=(),
            ),
        )

    async def test_constitutional_filter_loop(self) -> None:
        await self._assert_steps(
            ConstitutionalFilterLoop,
            ConstitutionalState(
                principles_text="- be kind",
                llm=_Llm(),
                evaluation_system="sys",
                max_revisions=2,
                current_content="draft",
                attempts=0,
                compliant=False,
            ),
        )

    async def test_json_extractor_loop(self) -> None:
        await self._assert_steps(
            JsonExtractorLoop,
            JsonExtractorState(
                prompt="p",
                llm=_Llm(),
                schema={"a": {"type": "string"}},
                max_retries=2,
                prior_error="",
                result=None,
                last_error="none",
                attempts=0,
            ),
        )

    async def test_yaml_extractor_loop(self) -> None:
        await self._assert_steps(
            YamlExtractorLoop,
            YamlExtractorState(
                prompt="p",
                llm=_Llm(),
                schema=None,
                max_retries=2,
                prior_error="",
                result=None,
                last_error="none",
                attempts=0,
            ),
        )

    async def test_pydantic_validator_loop(self) -> None:
        from pydantic import BaseModel

        class _Record(BaseModel):
            name: str

        await self._assert_steps(
            PydanticValidatorLoop,
            PydanticValidatorState(
                prompt="p",
                llm=_Llm(),
                schema={"name": {"type": "string"}},
                model_class=_Record,
                max_retries=2,
                prior_error="",
                validated=None,
                last_error="none",
                attempts=0,
            ),
        )

    async def test_retry_on_parse_failure_loop(self) -> None:
        await self._assert_steps(
            RetryOnParseFailureLoop,
            RetryState(
                original_prompt="p",
                llm=_Llm(),
                parser=str,
                max_retries=2,
                prompt="p",
                parsed_value=None,
                succeeded=False,
                last_error="none",
                attempts=0,
            ),
        )

    async def test_evaluator_optimizer_loop(self) -> None:
        await self._assert_steps(
            EvaluatorOptimizerLoop,
            EvaluatorOptimizerState(
                task="t", llm=_Llm(), threshold=0.8, max_iterations=2, reflection_gate=False
            ),
        )

    async def test_reflexion_loop(self) -> None:
        await self._assert_steps(
            ReflexionLoop,
            ReflexionState(
                task="t",
                llm=_Llm(),
                memory=_Store(),
                max_iterations=2,
                memory_namespace="ns",
                reflection_keys=(),
                attempts=(),
                final_answer="",
                succeeded=False,
                index=0,
            ),
        )

    async def test_flare_loop(self) -> None:
        await self._assert_steps(
            FlareLoop,
            FlareState(
                query="q",
                memory=_Store(),
                llm=_Llm(),
                confidence_threshold=0.5,
                max_sentences=2,
                max_retrieval_calls=1,
                top_k=3,
                parts=(),
                retrieval_calls=0,
                done=False,
                index=0,
            ),
        )

    async def test_agentic_rag_loop(self) -> None:
        await self._assert_steps(
            AgenticRagLoop,
            AgenticRagState(
                query="q",
                rag_tool=StubTool(name="rag", description="d", result="r"),
                llm=_Llm(),
                max_iterations=2,
                current_question="q",
            ),
        )

    async def test_iterative_retrieval_loop(self) -> None:
        await self._assert_steps(
            IterativeRetrievalLoop,
            IterativeRetrievalState(
                original_query="q",
                memory=_Store(),
                llm=_Llm(),
                max_iterations=2,
                top_k=3,
                current_query="q",
            ),
        )

    async def test_fallback_loop(self) -> None:
        loop = self._built(
            FallbackLoop,
            FallbackChainState(ordered=(), arguments={}, confidences={}),
        )
        # No candidates: the loop terminates from its state alone, without ever
        # reading an instance attribute.
        assert (
            await loop.astep(FallbackChainState(ordered=(), arguments={}, confidences={})) is None
        )

    async def test_cascade_loop(self) -> None:
        state = CascadeChainState(
            request="r",
            tiers=(),
            confidence=_unused_confidence,
            meter=None,
            spend_cap_policy=SpendCapPolicy.DOWNSHIFT,
        )
        loop = self._built(CascadeLoop, state)
        assert await loop.astep(state) is None


async def _unused_confidence(value: Any) -> float:
    """Scorer the no-tier cascade never calls."""
    return 1.0


class TestRoundRobinLoopIsDrivenByState(unittest.IsolatedAsyncioTestCase):
    """``RoundRobinLoop`` needs a reviewer ``SubTapestry``, so it stands apart."""

    async def test_no_reviewers_terminates_from_state_alone(self) -> None:
        from pirn_agents.specializations.multi_agent.round_robin_loop import RoundRobinLoop
        from pirn_agents.specializations.multi_agent.round_robin_state import RoundRobinState

        state = RoundRobinState(
            reviewers=(),
            response=AgentResponse(content="draft", finish_reason="stop"),
            index=0,
        )
        with Tapestry():
            loop = RoundRobinLoop(state=state, _config=KnotConfig(id="loop"))
        assert await loop.astep(state) is None


if __name__ == "__main__":
    unittest.main()
