"""``GeneratedResponse`` — the raw assistant reply plus its generation metadata.

Part of the ``examples.llm_agent.chatbot_pipeline`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GeneratedResponse:
    text: str
    model: str
    tokens_used: int
    finish_reason: str
