"""``SafetyResult`` — the moderation verdict for one user message.

Part of the ``examples.llm_agent.chatbot_pipeline`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SafetyResult:
    safe: bool
    reason: str | None = None
