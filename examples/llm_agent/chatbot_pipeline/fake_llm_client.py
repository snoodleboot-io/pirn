"""``FakeLLMClient`` — the simulated LLM API the knots call.

Part of the ``examples.llm_agent.chatbot_pipeline`` example.  Replace
:meth:`FakeLLMClient.call` with a real SDK call (anthropic, openai, …) to run
the same tapestry against a live model.
"""

from __future__ import annotations

import asyncio
import json
from typing import ClassVar


class FakeLLMClient:
    """A scripted stand-in for a chat-completions endpoint."""

    _latency_seconds: ClassVar[float] = 0.03
    _model: ClassVar[str] = "claude-sonnet-4-6"
    _retrieved_chunk: ClassVar[str] = (
        "Our Pro plan includes unlimited API calls and priority support."
    )

    @classmethod
    async def call(cls, system: str, user: str, max_tokens: int = 200) -> dict:
        """Simulates an LLM API call. Replace with real SDK calls."""
        await asyncio.sleep(cls._latency_seconds)  # simulate ~30ms API latency
        if "classify intent" in system.lower():
            return {"content": json.dumps({"label": "question", "confidence": 0.92})}
        if "extract entities" in system.lower():
            words = user.split()
            entities = [{"type": "TOPIC", "value": w} for w in words if len(w) > 5][:3]
            return {"content": json.dumps(entities)}
        if "retrieve" in system.lower():
            return {"content": cls._retrieved_chunk}
        # generation
        return {
            "content": f"Based on the context: {user[:80]}... Here is a helpful response.",
            "model": cls._model,
            "usage": {"input_tokens": 150, "output_tokens": 80},
            "stop_reason": "end_turn",
        }
