"""``_SelfAskComposer`` — compose the final answer from sub-question/answer pairs.

Replaces the inline ``_SelfAskResultSource(Source)`` that closed over an
already-computed :class:`SelfAskResult` (ADR agents-speaks-core WS5b;
PIR-856's imperative-loop inventory: a "returns inline Source" bypass, not
just the loop). This knot performs the composition call itself, so it is a
real, individually-traceable knot rather than a Source handing back an
answer Python already had.

Algorithm:
    1. Receive ``task``, the sub-answer loop's final ``state`` (a
       :class:`_SelfAskState`), and ``llm``.
    2. Render the sub-question/answer pairs and the compose system prompt.
    3. Call the LLM and extract its text, reporting the outcome through
       :class:`~pirn_agents.observability.agent_call_recorder.AgentCallRecorder`
       (ADR agents-speaks-core WS4a/WS5b).
    4. Return the composed :class:`~pirn_agents.specializations.self_ask.self_ask_result.SelfAskResult`.

Internal API. See PIR-856.
"""

from __future__ import annotations

import time
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.observability.agent_call_recorder import AgentCallRecorder
from pirn_agents.specializations.llm_response_text import LlmResponseText
from pirn_agents.specializations.self_ask._self_ask_state import _SelfAskState
from pirn_agents.specializations.self_ask.self_ask_result import SelfAskResult


class _SelfAskComposer(Knot):
    """Compose the final answer from the accumulated sub-question/answer pairs."""

    def __init__(
        self,
        *,
        task: Knot | str,
        state: Knot,
        llm: Knot | LLMProvider,
        compose_system: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            task=task,
            state=state,
            llm=llm,
            compose_system=compose_system,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        task: str,
        state: _SelfAskState,
        llm: LLMProvider,
        compose_system: str,
        **_: Any,
    ) -> SelfAskResult:
        """Compose the final answer and wrap it in a :class:`SelfAskResult`.

        Args:
            task: The original question.
            state: The sub-answer loop's final accumulated state.
            llm: Provider used for the composition call.
            compose_system: The system prompt instructing the LLM to compose.

        Returns:
            The composed :class:`SelfAskResult`.
        """
        pairs = "\n".join(
            f"Q: {q}\nA: {a}" for q, a in zip(state.subquestions, state.subanswers, strict=True)
        )
        start = time.perf_counter()
        try:
            final_raw = await llm.chat(
                messages=[
                    {"role": "system", "content": compose_system},
                    {"role": "user", "content": f"Question:\n{task}\n\n{pairs}"},
                ]
            )
        except Exception as exc:
            await AgentCallRecorder.record(
                knot_id=self.knot_id,
                kind="llm",
                ok=False,
                latency=time.perf_counter() - start,
                detail=str(exc),
            )
            raise
        await AgentCallRecorder.record(
            knot_id=self.knot_id,
            kind="llm",
            ok=True,
            latency=time.perf_counter() - start,
        )
        return SelfAskResult(
            final_answer=LlmResponseText().extract(final_raw),
            subquestions=state.subquestions,
            subanswers=state.subanswers,
        )
