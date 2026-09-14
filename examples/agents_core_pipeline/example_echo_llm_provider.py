"""``ExampleEchoLLMProvider`` — a deterministic, offline LLM provider for the example.

Part of the ``examples.agents_core_pipeline`` example.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Any

from pirn_agents.llm.llm_provider import LLMProvider
from pirn_agents.llm.stream_delta import StreamDelta


class ExampleEchoLLMProvider(LLMProvider):
    """Always answers ``"Final Answer: <reply>"`` — deterministic, offline.

    Exists only to satisfy ``react``'s required ``llm`` component without an
    API key or network access — not a template for a real provider (see
    ``pirn_agents.llm`` for the Anthropic/OpenAI-compatible ones).
    """

    def __init__(self, reply: str) -> None:
        self._reply = reply

    async def chat(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> Mapping[str, Any]:
        return {"role": "assistant", "content": f"Final Answer: {self._reply}"}

    def stream_chat(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> AsyncIterator[StreamDelta]:
        return self._one_chunk()

    async def _one_chunk(self) -> AsyncIterator[StreamDelta]:
        yield StreamDelta(content=f"Final Answer: {self._reply}")

    async def close(self) -> None:
        return None
