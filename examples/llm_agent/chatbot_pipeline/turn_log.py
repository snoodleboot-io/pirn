"""``TurnLog`` — structured turn metadata for analytics and debugging.

Part of the ``examples.llm_agent.chatbot_pipeline`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TurnLog:
    user_id: str
    session_id: str
    turn: int
    intent: str
    safe: bool
    response_length: int
