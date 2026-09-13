"""``_LLMCallKnot`` — internal single-prompt LLM call knot for RetryOnParseFailure.

Algorithm:
    1. Receive ``prompt`` (string) and ``llm`` provider.
    2. Frame the prompt as a single user chat message.
    3. Call the LLM provider and extract the text content from the response,
       reporting the outcome through
       :class:`~pirn_agents.observability.agent_call_recorder.AgentCallRecorder`
       (ADR agents-speaks-core WS4a/WS5b).
    4. Return the extracted text string.


References:
    - :class:`pirn_agents.llm.llm_provider.LLMProvider`
"""

from __future__ import annotations

import time
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.observability.agent_call_recorder import AgentCallRecorder
from pirn_agents.specializations.llm_response_text import LlmResponseText


class _LLMCallKnot(Knot):
    """Inner knot that calls the LLM with a single prompt string."""

    def __init__(
        self,
        *,
        prompt: Knot | str,
        llm: Knot | LLMProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(prompt=prompt, llm=llm, _config=_config, **kwargs)

    async def process(self, prompt: str, llm: LLMProvider, **_: Any) -> str:
        """Call the LLM and return the text content of the response.

        Args:
            prompt: The prompt string sent to the LLM as a user message.
            llm: The LLM provider to call.

        Returns:
            The text content returned by the LLM.
        """
        start = time.perf_counter()
        try:
            raw = await llm.chat([{"role": "user", "content": prompt}])
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
        return LlmResponseText().extract(raw)
