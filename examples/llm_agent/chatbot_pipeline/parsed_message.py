"""``ParsedMessage`` — the normalised incoming turn.

Part of the ``examples.llm_agent.chatbot_pipeline`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ParsedMessage:
    text: str
    user_id: str
    session_id: str
    turn_number: int
