"""``PostProcessedResponse`` — the formatted reply with its source citations.

Part of the ``examples.llm_agent.chatbot_pipeline`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PostProcessedResponse:
    text: str
    citations: list[str]
