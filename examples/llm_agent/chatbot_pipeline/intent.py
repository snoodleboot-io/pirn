"""``Intent`` — the classifier's label and confidence.

Part of the ``examples.llm_agent.chatbot_pipeline`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Intent:
    label: str  # e.g. "question", "command", "chitchat", "complaint"
    confidence: float
