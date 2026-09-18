"""``ScriptedLLMProvider`` — a scripted, offline ``LLMProvider`` for the example.

Part of the ``examples.llm_agent.agent_loop_v2`` example.  Swap it for a real
provider by implementing ``LLMProvider.chat`` against your vendor SDK.
"""

from __future__ import annotations

import hashlib
from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Any, ClassVar

from pirn_agents.llm.llm_provider import LLMProvider


class ScriptedLLMProvider(LLMProvider):
    """Scripted LLM double — deterministic, no network required.

    Responses cycle through a fixed pool keyed by the last user message
    so the output is always the same given the same input.
    """

    _pool: ClassVar[tuple[str, ...]] = (
        "I have gathered the relevant information and can now summarise: "
        "the data indicates a clear trend over the past quarter.",
        "After reasoning through the available context I conclude that "
        "the best course of action is to proceed with the staged rollout.",
        "Final Answer: Based on the evidence gathered the primary "
        "finding is a 12% improvement in throughput after the change.",
        "The analysis is complete. Three key factors emerge: latency, "
        "throughput, and error rate — all improved post-deployment.",
        "Research complete. The topic has been investigated across "
        "five sources; consensus points to option B as the stronger "
        "approach given the current constraints.",
    )

    def __init__(self, seed: int = 0) -> None:
        self._seed = seed

    async def chat(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> Mapping[str, Any]:
        last = next(
            (m["content"] for m in reversed(messages) if m.get("role") == "user"),
            "",
        )
        idx = int(hashlib.md5(f"{last}{self._seed}".encode()).hexdigest(), 16)
        text = self._pool[idx % len(self._pool)]
        return {"role": "assistant", "content": text}

    async def stream_chat(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> AsyncIterator[Mapping[str, Any]]:
        resp = await self.chat(messages)
        return self._one_chunk(resp["content"])

    @staticmethod
    async def _one_chunk(content: Any) -> AsyncIterator[Mapping[str, Any]]:
        """The whole scripted reply as a single stream chunk."""
        yield {"content": content}

    async def close(self) -> None:
        return None
