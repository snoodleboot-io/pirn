"""``RecordedLlmCall`` — one provider ``chat()`` reported through ``AgentCallRecorder``.

A knot that talks to an :class:`~pirn_agents.llm.llm_provider.LLMProvider`
inside its ``process()`` makes a call the engine cannot see: the knot's own
lifecycle transition says it ran, not that a model was consulted, how long
that took, or whether the provider raised.  Since the ADR "agents speaks core"
(WS4a) that call is reported as its own ``StatusEvent`` through
:class:`~pirn_agents.observability.agent_call_recorder.AgentCallRecorder`;
this class is the one place the timing and the success/failure split live so
every LLM-calling knot in the tools lane reports the same shape.
"""

from __future__ import annotations

import time
from collections.abc import Mapping, Sequence
from typing import Any

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.observability.agent_call_recorder import AgentCallRecorder


class RecordedLlmCall:
    """Run one ``LLMProvider.chat`` and emit its outcome as an ``"llm"`` call event."""

    @staticmethod
    async def chat(
        *,
        knot_id: str,
        llm: LLMProvider,
        messages: Sequence[Mapping[str, Any]],
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> Mapping[str, Any]:
        """Call ``llm.chat`` and record the call under ``knot_id``.

        The provider's raw response is returned unchanged and a raised
        exception propagates unchanged; either way one event is emitted (a
        no-op outside a run) carrying the elapsed time and, for a failure,
        the exception's type and message as ``detail``.

        Args:
            knot_id: The calling knot's ``knot_id``.
            llm: The provider to call.
            messages: The chat messages, provider-neutral wire shape.
            model: Optional model override, forwarded and reported.
            max_tokens: Optional token cap, forwarded.
            temperature: Optional sampling temperature, forwarded.
        """
        start = time.perf_counter()
        try:
            response = await llm.chat(
                messages, model=model, max_tokens=max_tokens, temperature=temperature
            )
        except Exception as exc:
            await AgentCallRecorder.record(
                knot_id=knot_id,
                kind="llm",
                ok=False,
                latency=time.perf_counter() - start,
                detail=f"{type(exc).__name__}: {exc}",
                model=model,
            )
            raise
        await AgentCallRecorder.record(
            knot_id=knot_id,
            kind="llm",
            ok=True,
            latency=time.perf_counter() - start,
            model=model,
        )
        return response
